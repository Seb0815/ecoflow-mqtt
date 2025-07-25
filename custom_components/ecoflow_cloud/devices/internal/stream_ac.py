from custom_components.ecoflow_cloud.api import EcoflowApiClient
from custom_components.ecoflow_cloud.devices import const, BaseDevice
import datetime
import logging

_LOGGER = logging.getLogger(__name__)

class StreamAC(BaseDevice):
    """Stream AC/Ultra Gerät - Vereinfacht für MQTT Publishing"""
    
    def _prepare_data_get_topic(self, raw_data) -> dict[str, any]:
        return super()._prepare_data(raw_data)

    def _prepare_data(self, raw_data) -> dict[str, any]:
        """Haupt-Parsing-Methode für Stream AC/Ultra Protobuf-Daten - robuste Version"""
        raw = {"params": {}}
        
        try:
            from .proto import ecopacket_pb2 as ecopacket, stream_ac_pb2 as stream_ac
            
            payload = raw_data
            _LOGGER.debug("Processing Stream payload: %s bytes", len(payload))
            
            # Versuche Stream-spezifische Dekodierung
            packet = stream_ac.SendHeaderStreamMsg()
            packet.ParseFromString(payload)
            
            _LOGGER.debug("Stream packet parsed successfully")
            
            if hasattr(packet.msg, "pdata") and len(packet.msg.pdata) > 0:
                _LOGGER.debug("Found pdata: %s bytes", len(packet.msg.pdata))
                
                # Versuche verschiedene Stream-Message-Typen
                pdata = packet.msg.pdata
                parsed_data = self._parse_stream_pdata_safe(pdata)
                if parsed_data:
                    raw["params"].update(parsed_data)
                    _LOGGER.info("Successfully parsed %d Stream parameters", len(parsed_data))
                else:
                    _LOGGER.debug("No Stream parameters extracted")
            
            if hasattr(packet.msg, 'cmd_id'):
                raw["params"]["cmd_id"] = packet.msg.cmd_id
            if hasattr(packet.msg, 'cmd_func'):
                raw["params"]["cmd_func"] = packet.msg.cmd_func
                
            raw["timestamp"] = datetime.datetime.now(datetime.timezone.utc)
            
        except Exception as error:
            _LOGGER.error("Stream _prepare_data failed: %s", error)
            _LOGGER.debug("Raw data hex: %s", raw_data.hex())
            # Fallback: Grundlegende Hex-Informationen
            raw["params"]["error"] = str(error)
            raw["params"]["raw_hex"] = raw_data.hex()
            raw["params"]["raw_length"] = len(raw_data)
        
        return raw

    def _parse_stream_pdata_safe(self, pdata: bytes) -> dict:
        """Sichere Parsing-Methode für Stream pdata"""
        try:
            from .proto import stream_ac_pb2 as stream_ac
            
            result = {}
            
            # Liste der Stream-Message-Typen
            stream_types = [
                ("HeaderStream", stream_ac.HeaderStream),
                ("Champ_cmd21", stream_ac.Champ_cmd21), 
                ("Champ_cmd21_3", stream_ac.Champ_cmd21_3),
                ("Champ_cmd50", stream_ac.Champ_cmd50),
                ("Champ_cmd50_3", stream_ac.Champ_cmd50_3)
            ]
            
            for stream_name, stream_class in stream_types:
                try:
                    content = stream_class()
                    content.ParseFromString(pdata)
                    
                    # Prüfe ob Inhalt vorhanden ist
                    content_str = str(content)
                    if len(content_str) > 0 and content_str.strip():
                        _LOGGER.debug("Successfully parsed %s", stream_name)
                        
                        # Extrahiere Felder mit gleicher Logik wie original
                        for descriptor in content.DESCRIPTOR.fields:
                            try:
                                if not content.HasField(descriptor.name):
                                    continue
                                
                                value = getattr(content, descriptor.name)
                                field_name = descriptor.name
                                
                                # Stream AC Parameter-Verarbeitung
                                if field_name == "f32ShowSoc":
                                    result["battery_soc"] = round(value, 2)
                                    result["f32ShowSoc"] = value
                                elif field_name == "bmsBattSoc":
                                    result["bms_battery_soc"] = round(value, 2)
                                    result["bmsBattSoc"] = value
                                elif field_name == "soc":
                                    result["soc"] = value
                                    result["battery_percentage"] = value
                                elif field_name in ["bmsChgRemTime", "bmsDsgRemTime"]:
                                    result[field_name] = value
                                    if field_name == "bmsChgRemTime":
                                        result["charge_remaining_minutes"] = value
                                    elif field_name == "bmsDsgRemTime":
                                        result["discharge_remaining_minutes"] = value
                                elif field_name == "cycles":
                                    result["battery_cycles"] = value
                                    result["cycles"] = value
                                elif field_name in ["designCap", "fullCap", "remainCap"]:
                                    result[field_name] = value
                                elif field_name in ["gridConnectionPower", "inputWatts", "outputWatts"]:
                                    result[field_name] = round(value, 2)
                                elif field_name in ["powGetPvSum", "powGetBpCms", "powGetSysGrid"]:
                                    result[field_name] = round(value, 2)
                                elif field_name in ["maxCellTemp", "minCellTemp", "temp"]:
                                    result[field_name] = value
                                elif field_name in ["maxCellVol", "minCellVol", "vol"]:
                                    result[field_name] = value
                                else:
                                    result[field_name] = value
                                    
                            except Exception as field_error:
                                _LOGGER.debug("Failed to process field %s: %s", descriptor.name, field_error)
                                continue
                        
                        # Wenn wir wichtige Parameter gefunden haben, sind wir erfolgreich
                        if any(key in result for key in ["battery_soc", "soc", "battery_percentage"]):
                            _LOGGER.info("Found key battery parameters in %s", stream_name)
                            break
                
                except Exception as e:
                    _LOGGER.debug("Failed to parse %s: %s", stream_name, e)
                    continue
            
            return result
            
        except Exception as e:
            _LOGGER.debug("Stream pdata parsing failed: %s", e)
            return {}

    # Ende der Klasse