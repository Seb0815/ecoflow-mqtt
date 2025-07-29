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
    
    @classmethod
    def get_defined_parameters(cls) -> set:
        """
        Extrahiert alle definierten Parameter aus dieser Device-Klasse
        Muss von Subklassen überschrieben werden oder nutzt Sensor-Extraktion
        """
        # Versuche automatische Extraktion aus sensors() Methode
        try:
            from ..sensor import extract_sensor_parameters_from_device_class
            return extract_sensor_parameters_from_device_class(cls)
        except ImportError:
            return set()
    
    def analyze_missing_parameters(self, received_params: dict, hex_data: str = None) -> dict:
        """
        Analysiert fehlende Parameter und gibt Verbesserungsvorschläge für Device-Klassen
        """
        try:
            defined_params = self.get_defined_parameters()
            received_param_names = set(received_params.keys())
            missing_params = defined_params - received_param_names
            
            analysis = {
                "device_type": self.__class__.__name__,
                "defined_count": len(defined_params),
                "received_count": len(received_param_names),
                "missing_count": len(missing_params),
                "missing_params": sorted(list(missing_params)),
                "suggestions": []
            }
            
            _LOGGER.info(f"{self.__class__.__name__}: {len(defined_params)} defined, {len(received_param_names)} received, {len(missing_params)} missing")
            
            if missing_params and hex_data:
                candidates = self._extract_parameter_candidates(hex_data, missing_params)
                analysis["hex_candidates"] = candidates
                analysis["suggestions"] = self._generate_device_class_suggestions(missing_params, candidates)
            
            return analysis
            
        except Exception as e:
            _LOGGER.debug(f"Failed to analyze missing parameters: {e}")
            return {"error": str(e)}
    
    def _extract_parameter_candidates(self, hex_data: str, missing_params: set) -> dict:
        """
        Extrahiert Parameter-Kandidaten aus Hex-Daten basierend auf fehlenden Parametern
        """
        candidates = {}
        
        try:
            data = bytes.fromhex(hex_data)
            
            for i in range(0, len(data) - 3, 2):
                if i + 3 < len(data):
                    value16_le = int.from_bytes(data[i:i+2], byteorder='little')
                    value16_be = int.from_bytes(data[i:i+2], byteorder='big')
                    if i + 3 < len(data):
                        value32_le = int.from_bytes(data[i:i+4], byteorder='little')
                    
                    # Parameter-spezifische Heuristiken
                    self._check_soc_candidates(missing_params, value16_le, i, candidates)
                    self._check_voltage_candidates(missing_params, value16_le, i, candidates)
                    self._check_temperature_candidates(missing_params, value16_le, i, candidates)
                    self._check_power_candidates(missing_params, value16_le, i, candidates)
                    self._check_capacity_candidates(missing_params, value32_le, i, candidates)
                    
        except Exception as e:
            _LOGGER.debug(f"Failed to extract parameter candidates: {e}")
            
        return candidates
    
    def _check_soc_candidates(self, missing_params: set, value: int, position: int, candidates: dict):
        soc_params = [p for p in missing_params if 'soc' in p.lower()]
        if soc_params and 0 <= value <= 100 and value != 0:
            candidates[f"soc_candidate_@{position}"] = {"value": value, "matches": soc_params[:3]}
    
    def _check_voltage_candidates(self, missing_params: set, value: int, position: int, candidates: dict):
        volt_params = [p for p in missing_params if any(v in p.lower() for v in ['vol', 'volt'])]
        if volt_params and 3000 <= value <= 4200:
            candidates[f"voltage_mv_candidate_@{position}"] = {"value": value, "matches": volt_params[:3]}
    
    def _check_temperature_candidates(self, missing_params: set, value: int, position: int, candidates: dict):
        temp_params = [p for p in missing_params if 'temp' in p.lower()]
        if temp_params and 15 <= value <= 80:
            candidates[f"temperature_c_candidate_@{position}"] = {"value": value, "matches": temp_params[:3]}
    
    def _check_power_candidates(self, missing_params: set, value: int, position: int, candidates: dict):
        power_params = [p for p in missing_params if any(keyword in p.lower() for keyword in ['power', 'watt', 'get', 'out', 'in'])]
        if power_params and 0 <= value <= 5000 and value > 5:
            candidates[f"power_w_candidate_@{position}"] = {"value": value, "matches": power_params[:3]}
    
    def _check_capacity_candidates(self, missing_params: set, value: int, position: int, candidates: dict):
        cap_params = [p for p in missing_params if 'cap' in p.lower()]
        if cap_params and 1000 <= value <= 200000:
            candidates[f"capacity_mah_candidate_@{position}"] = {"value": value, "matches": cap_params[:3]}
    
    def _generate_device_class_suggestions(self, missing_params: set, candidates: dict) -> list:
        """
        Generiert konkrete Vorschläge zur Erweiterung der Device-Klasse
        """
        suggestions = []
        
        # Gruppiere Vorschläge nach Parameter-Typ
        param_types = {
            "soc": [p for p in missing_params if 'soc' in p.lower()],
            "voltage": [p for p in missing_params if any(v in p.lower() for v in ['vol', 'volt'])],
            "temperature": [p for p in missing_params if 'temp' in p.lower()],
            "power": [p for p in missing_params if any(k in p.lower() for k in ['power', 'watt', 'get', 'out', 'in'])],
            "capacity": [p for p in missing_params if 'cap' in p.lower()]
        }
        
        for param_type, params in param_types.items():
            if params and any(param_type in c for c in candidates.keys()):
                matching_candidates = [c for c in candidates.keys() if param_type in c]
                if matching_candidates:
                    suggestions.append(f"Add {param_type} sensors for: {params[:3]} (found candidates: {len(matching_candidates)})")
        
        return suggestions


class DiagnosticDevice(BaseDevice):
    """Diagnostisches Gerät für unbekannte Device-Types - Vereinfacht für MQTT"""
    pass
