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
                    
                    # Debug: Liste alle geparsten Parameter auf
                    for key, value in parsed_data.items():
                        _LOGGER.debug(f"📊 Stream parameter: {key} = {value}")
                        # Spezielle Behandlung für enc_type
                        if key == "enc_type":
                            _LOGGER.warning(f"🚨 Found enc_type in Stream parameters: {value} (this should be a header field!)")
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
                        _LOGGER.info(f"✅ Successfully parsed {stream_name} - Content length: {len(content_str)}")
                        
                        # Debug: Zeige verfügbare Felder
                        available_fields = [f.name for f in content.DESCRIPTOR.fields if content.HasField(f.name)]
                        _LOGGER.info(f"📋 Available fields in {stream_name}: {available_fields}")
                        
                        # Extrahiere Felder mit gleicher Logik wie original
                        for descriptor in content.DESCRIPTOR.fields:
                            try:
                                if not content.HasField(descriptor.name):
                                    continue
                                
                                value = getattr(content, descriptor.name)
                                field_name = descriptor.name
                                
                                # ❌ WICHTIG: Header-Felder herausfiltern!
                                # Diese Felder gehören zum Protobuf-Header, nicht zu den Gerätedaten
                                header_fields = {
                                    "src", "dest", "d_src", "d_dest", "check_type", 
                                    "cmd_func", "cmd_id", "data_len", "need_ack", "is_ack", 
                                    "seq", "product_id", "version", "payload_ver", "time_snap", 
                                    "is_rw_cmd", "is_queue", "ack_type", "code", "from", 
                                    "module_sn", "device_sn", "pdata"
                                    # HINWEIS: enc_type NICHT hier - es könnte Battery SOC sein!
                                }
                                
                                if field_name in header_fields:
                                    _LOGGER.info(f"🚫 Filtering header field: {field_name} = {value}")
                                    continue
                                
                                # ✅ Alle anderen Felder protokollieren
                                _LOGGER.info(f"✅ Processing field: {field_name} = {value}")
                                
                                # 🔋 SPEZIELLE BEHANDLUNG für enc_type als Battery SOC
                                if field_name == "enc_type":
                                    # enc_type scheint der echte Battery SOC zu sein (0-100%)
                                    if 0 <= value <= 100:
                                        result["battery_soc"] = value
                                        result["battery_percentage"] = value
                                        result["enc_type_raw"] = value
                                        _LOGGER.info(f"🔋 Battery SOC from enc_type: {value}%")
                                    else:
                                        _LOGGER.warning(f"⚠️ enc_type out of range for SOC: {value}")
                                        result["enc_type_unknown"] = value
                                
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
                                elif field_name == "Champ_cmd21_3_field460":
                                    # Dieser Wert ist NICHT der Battery SOC - das war ein Irrtum
                                    result["field460_raw"] = value
                                    result["field460_converted"] = round(value / 100.0, 2)
                                    _LOGGER.info(f"� Field460 (not SOC): {value} raw -> {round(value / 100.0, 2)}")
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
                                    _LOGGER.info(f"⚡ Power parameter: {field_name} = {value}W")
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