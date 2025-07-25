#!/usr/bin/env python3
"""
EcoFlow Cloud MQTT Publisher - Standalone Version
Publiziert EcoFlow Gerätedaten über MQTT ohne Home Assistant Abhängigkeiten
"""

import asyncio
import json
import logging
import os
import signal
import struct
import sys
import time
import traceback
import datetime
from typing import Dict

import paho.mqtt.client as mqtt

# EcoFlow API Imports
from custom_components.ecoflow_cloud.api.private_api import EcoflowPrivateApiClient
from custom_components.ecoflow_cloud.api.public_api import EcoflowPublicApiClient
from custom_components.ecoflow_cloud.device_data import DeviceData, DeviceOptions

# Logging Setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
_LOGGER = logging.getLogger(__name__)


class EcoflowMqttPublisher:
    """EcoFlow MQTT Publisher mit Device-Klassen Integration"""
    
    def __init__(self):
        self.api_client = None
        self.mqtt_client = None
        self.running = False
        self.devices = {}  # Device-Instanzen für jede Seriennummer
        
        # Konfiguration aus Umgebungsvariablen laden
        self.load_config()

    def load_config(self):
        """Lädt Konfiguration aus Umgebungsvariablen"""
        # EcoFlow API Konfiguration (verwende immer private API)
        self.username = os.getenv("ECOFLOW_USERNAME")
        self.password = os.getenv("ECOFLOW_PASSWORD")
        
        if not self.username or not self.password:
            raise ValueError("ECOFLOW_USERNAME und ECOFLOW_PASSWORD müssen gesetzt sein")
        
        # Device Liste (kommagetrennt)
        self.device_sns = [sn.strip() for sn in os.getenv("ECOFLOW_DEVICES", "").split(",") if sn.strip()]
        
        # MQTT Konfiguration
        self.mqtt_host = os.getenv("MQTT_HOST", "localhost")
        self.mqtt_port = int(os.getenv("MQTT_PORT", "1883"))
        self.mqtt_username = os.getenv("MQTT_USERNAME")
        self.mqtt_password = os.getenv("MQTT_PASSWORD")
        self.mqtt_base_topic = os.getenv("MQTT_BASE_TOPIC", "ecoflow")

    async def setup_api_client(self):
        """Erstellt EcoFlow API Client"""
        self.api_client = EcoflowPrivateApiClient(
            "api.ecoflow.com",
            self.username,
            self.password,
            "v1"
        )
        
        # Seriennummern an API Client weitergeben für MQTT Topics
        self.api_client.device_sns = self.device_sns
        
        # Login durchführen
        await self.api_client.login()
        _LOGGER.info("Successfully logged in to EcoFlow API")
        
        # Device-Instanzen erstellen basierend auf den Seriennummern
        await self.setup_device_instances()
        
        # MQTT Client starten
        await asyncio.get_event_loop().run_in_executor(None, self.api_client.start)
        _LOGGER.info("EcoFlow MQTT Client started")

    async def setup_device_instances(self):
        """Erstellt Device-Instanzen für alle konfigurierten Geräte"""
        from custom_components.ecoflow_cloud.devices import EcoflowDeviceInfo, BaseDevice
        from custom_components.ecoflow_cloud.device_data import DeviceData, DeviceOptions
        
        for device_sn in self.device_sns:
            try:
                # Automatische Geräteerkennung
                device_type = self.detect_device_type(device_sn)
                
                # Device-Klasse importieren
                device_class = self.get_device_class(device_type)
                
                # DeviceInfo erstellen
                device_info = EcoflowDeviceInfo(
                    public_api=False,  # Nutzen private API
                    sn=device_sn,
                    name=f"EcoFlow {device_type}",
                    device_type=device_type,
                    status=1,
                    data_topic=f"/app/device/property/{device_sn}",
                    set_topic=f"/app/device/property/{device_sn}/set",
                    set_reply_topic=f"/app/device/property/{device_sn}/set_reply",
                    get_topic=f"/app/device/property/{device_sn}/get",
                    get_reply_topic=f"/app/device/property/{device_sn}/get_reply",
                    status_topic=f"/app/device/status/{device_sn}"
                )
                
                # DeviceData mit Optionen erstellen
                device_options = DeviceOptions(
                    refresh_period=30,
                    power_step=100,
                    diagnostic_mode=False
                )
                device_data = DeviceData(
                    sn=device_sn,
                    name=f"EcoFlow {device_type}",
                    device_type=device_type,
                    options=device_options,
                    display_name=f"EcoFlow {device_type} ({device_sn})",
                    parent=None
                )
                
                # Device-Instanz erstellen
                device_instance = device_class(device_info, device_data)
                self.devices[device_sn] = device_instance
                
                _LOGGER.info(f"✅ Created {device_type} device instance for {device_sn}")
                
            except Exception as e:
                _LOGGER.error(f"❌ Failed to create device instance for {device_sn}: {e}")
                # Fallback: Nutze DiagnosticDevice
                from custom_components.ecoflow_cloud.devices import DiagnosticDevice
                self.devices[device_sn] = None  # Placeholder
        
        _LOGGER.info(f"Created {len([d for d in self.devices.values() if d is not None])} device instances")

    def get_device_class(self, device_type: str):
        """Lädt die entsprechende Device-Klasse basierend auf dem Gerätetyp"""
        device_map = {
            "DELTA_2": "delta2.Delta2",
            "DELTA_2_MAX": "delta2_max.Delta2Max", 
            "DELTA_PRO": "delta_pro.DeltaPro",
            "DELTA_MAX": "delta_max.DeltaMax",
            "DELTA_MINI": "delta_mini.DeltaMini",
            "RIVER_2": "river2.River2",
            "RIVER_2_MAX": "river2_max.River2Max",
            "RIVER_2_PRO": "river2_pro.River2Pro", 
            "RIVER_MAX": "river_max.RiverMax",
            "RIVER_MINI": "river_mini.RiverMini",
            "RIVER_PRO": "river_pro.RiverPro",
            "POWERSTREAM": "powerstream.PowerStream",
            "STREAM_AC": "stream_ac.StreamAC",
            "STREAM_ULTRA": "stream_ac.StreamAC",  # Stream Ultra nutzt StreamAC Klasse
            "STREAM_PRO": "stream_ac.StreamAC",
            "GLACIER": "glacier.Glacier",
            "WAVE_2": "wave2.Wave2",
            "SMART_METER": "smart_meter.SmartMeter",
        }
        
        if device_type not in device_map:
            _LOGGER.warning(f"Unknown device type: {device_type}, using DiagnosticDevice")
            from custom_components.ecoflow_cloud.devices import DiagnosticDevice
            return DiagnosticDevice
        
        # Dynamischer Import der Device-Klasse
        module_path, class_name = device_map[device_type].rsplit('.', 1)
        try:
            module = __import__(f"custom_components.ecoflow_cloud.devices.internal.{module_path}", fromlist=[class_name])
            device_class = getattr(module, class_name)
            _LOGGER.info(f"Successfully loaded device class: {device_type} -> {class_name}")
            return device_class
        except Exception as e:
            _LOGGER.warning(f"Failed to load {device_type} device class: {e}, using DiagnosticDevice")
            from custom_components.ecoflow_cloud.devices import DiagnosticDevice
            return DiagnosticDevice

    def setup_mqtt_client(self):
        """Konfiguriert den lokalen MQTT Client"""
        self.mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
        
        if self.mqtt_username and self.mqtt_password:
            self.mqtt_client.username_pw_set(self.mqtt_username, self.mqtt_password)
            
        self.mqtt_client.on_connect = self.on_mqtt_connect
        self.mqtt_client.on_disconnect = self.on_mqtt_disconnect
        
        try:
            self.mqtt_client.connect(self.mqtt_host, self.mqtt_port, 60)
            self.mqtt_client.loop_start()
            _LOGGER.info(f"Connected to local MQTT broker: {self.mqtt_host}:{self.mqtt_port}")
        except Exception as e:
            _LOGGER.error(f"Error connecting to MQTT broker: {e}")
            raise

    def on_mqtt_connect(self, client, userdata, flags, rc):
        """Callback für MQTT Verbindung"""
        if rc == 0:
            _LOGGER.info("Successfully connected to local MQTT broker")
        else:
            _LOGGER.error(f"MQTT connection failed with code: {rc}")

    def on_mqtt_disconnect(self, client, userdata, rc):
        """Callback für MQTT Trennung"""
        _LOGGER.warning(f"MQTT connection disconnected with code: {rc}")

    def setup_ecoflow_message_forwarding(self):
        """Setup Message Forwarding vom EcoFlow MQTT zum lokalen Broker"""
        if hasattr(self.api_client, 'mqtt_client') and self.api_client.mqtt_client:
            # Zugriff auf den inneren paho-mqtt Client
            ecoflow_paho_client = None
            if hasattr(self.api_client.mqtt_client, '_EcoflowMQTTClient__client'):
                ecoflow_paho_client = self.api_client.mqtt_client._EcoflowMQTTClient__client
            elif hasattr(self.api_client.mqtt_client, '__client'):
                ecoflow_paho_client = self.api_client.mqtt_client.__client
            
            if ecoflow_paho_client:
                # Original-Callback sichern
                original_on_message = ecoflow_paho_client.on_message
                original_on_connect = ecoflow_paho_client.on_connect
                
                # Verbindungsüberwachung hinzufügen
                def connection_wrapper(client, userdata, flags, rc):
                    if rc == 0:
                        _LOGGER.info("🔗 EcoFlow MQTT broker connection successfully established")
                    else:
                        _LOGGER.warning(f"⚠️ EcoFlow MQTT connection failed: RC={rc}")
                    
                    # Original-Callback ausführen
                    if original_on_connect:
                        original_on_connect(client, userdata, flags, rc)
                
                # Wrapper-Callback erstellen
                def message_wrapper(client, userdata, message):
                    # Original-Callback ausführen
                    if original_on_message:
                        original_on_message(client, userdata, message)
                    
                    # Unsere eigene Verarbeitung
                    self.on_ecoflow_message(client, userdata, message)
                
                # Wrapper setzen
                ecoflow_paho_client.on_message = message_wrapper
                ecoflow_paho_client.on_connect = connection_wrapper
                _LOGGER.info("EcoFlow MQTT message handler successfully set")
                
                # Debug: MQTT-Client Status überprüfen (initial)
                _LOGGER.info(f"🐛 EcoFlow MQTT Client initial status: Connected={ecoflow_paho_client.is_connected()}")
                if hasattr(ecoflow_paho_client, '_host'):
                    _LOGGER.info(f"🐛 EcoFlow MQTT Client host: {ecoflow_paho_client._host}")
                
            else:
                _LOGGER.warning("Could not access EcoFlow paho-mqtt client")
        else:
            _LOGGER.warning("EcoFlow MQTT client not available")

    def on_ecoflow_message(self, client, userdata, message):
        """Callback für EcoFlow MQTT-Nachrichten - nutzt Device-Klassen für Dekodierung"""
        try:
            # Nachrichten-Statistik aktualisieren
            self.message_count = getattr(self, 'message_count', 0) + 1
            self.last_message_time = time.time()
            
            topic = message.topic
            payload = message.payload
            
            _LOGGER.info(f"📨 EcoFlow MQTT message #{self.message_count} received - Topic: {topic}, Payload size: {len(payload)} bytes")
            
            # Versuche Geräte-SN zu extrahieren
            device_sn = None
            for sn in self.device_sns:
                if sn in topic:
                    device_sn = sn
                    break
            
            if not device_sn:
                _LOGGER.warning(f"No device SN found in topic: {topic}")
                return
            
            # Device-Instanz holen
            device_instance = self.devices.get(device_sn)
            if not device_instance:
                _LOGGER.warning(f"No device instance found for {device_sn}")
                return
            
            device_type = self.detect_device_type(device_sn)
            _LOGGER.info(f"Processing message for {device_type} ({device_sn}) - Topic: {topic}")
            
            # Device-spezifische Dekodierung mit der echten Device-Klasse
            decoded_data = self.decode_with_device_class(device_instance, device_sn, device_type, payload)
            
            if decoded_data and "params" in decoded_data and decoded_data["params"]:
                param_count = len(decoded_data["params"])
                _LOGGER.info(f"✅ Device class decoded {device_type} data: {param_count} parameters")
                
                # Detaillierte Parameter-Info für wichtige Werte
                important_params = self.extract_important_parameters(decoded_data["params"])
                if important_params:
                    _LOGGER.info(f"🎯 Key parameters: {', '.join(important_params)}")
                
                # JSON für MQTT erstellen
                mqtt_data = {
                    "device_sn": device_sn,
                    "device_type": device_type,
                    "timestamp": time.time(),
                    "decoding_method": "device_class",
                    "message_count": self.message_count,
                    "params": decoded_data["params"]
                }
                
                # Rohdaten optional hinzufügen (für Debugging)
                if len(payload) < 1000:  # Nur bei kleinen Payloads
                    mqtt_data["raw_hex"] = payload.hex()
                    mqtt_data["raw_bytes"] = len(payload)
                
                payload_str = json.dumps(mqtt_data, indent=2, ensure_ascii=False, default=str)
                
            else:
                # Fallback: Als hex-string mit Gerätetyp
                _LOGGER.warning(f"⚠️ Device class decoding failed for {device_type}, using hex fallback")
                mqtt_data = {
                    "device_sn": device_sn,
                    "device_type": device_type,
                    "timestamp": time.time(),
                    "decoding_method": "hex_fallback",
                    "message_count": self.message_count,
                    "raw_hex": payload.hex(),
                    "raw_bytes": len(payload),
                    "params": {}
                }
                payload_str = json.dumps(mqtt_data, indent=2)
            
            # Weiterleitung an lokalen MQTT Broker
            local_topic = f"{self.mqtt_base_topic}/{device_sn}/data"
            self.mqtt_client.publish(local_topic, payload_str, retain=True)
            
            # Geräte-spezifisches Topic
            device_topic = f"{self.mqtt_base_topic}/{device_type.lower()}/{device_sn}/data"
            self.mqtt_client.publish(device_topic, payload_str, retain=True)
            
            # Parameter-spezifische Topics für ALLE Werte
            if "params" in mqtt_data and mqtt_data["params"]:
                self.publish_all_parameters(device_sn, device_type, mqtt_data["params"], mqtt_data.get("timestamp", time.time()))
            
            # Auch Original-Topic Structure beibehalten
            clean_topic = topic.replace("/app/", "").replace("+", "unknown")
            local_orig_topic = f"{self.mqtt_base_topic}/raw/{clean_topic}"
            self.mqtt_client.publish(local_orig_topic, payload_str, retain=True)
            
            _LOGGER.info(f"� EcoFlow {device_type} data forwarded: {topic} -> {local_topic}")
                
        except Exception as e:
            _LOGGER.error(f"Error forwarding EcoFlow message: {e}")
            import traceback
            _LOGGER.error(traceback.format_exc())

    def decode_with_device_class(self, device_instance, device_sn: str, device_type: str, payload: bytes) -> dict:
        """Nutzt die echte Device-Klasse für die Protobuf-Dekodierung"""
        try:
            # Basis-Struktur
            result = {
                "device_sn": device_sn,
                "device_type": device_type,
                "timestamp": time.time(),
                "params": {}
            }
            
            # Device-Klasse für Dekodierung nutzen
            if hasattr(device_instance, '_prepare_data'):
                # Device hat eigene _prepare_data Methode (wie StreamAC)
                decoded_raw = device_instance._prepare_data(payload)
                
                if decoded_raw and "params" in decoded_raw:
                    result["params"] = decoded_raw["params"]
                    result["decoding_success"] = True
                    _LOGGER.info(f"✅ Device class _prepare_data successful: {len(result['params'])} parameters")
                else:
                    _LOGGER.debug(f"Device _prepare_data returned no params")
                    result["decoding_success"] = False
                    
            elif hasattr(device_instance, 'data') and hasattr(device_instance.data, 'update_data'):
                # Standard BaseDevice mit EcoflowDataHolder
                # Simuliere update_data Aufruf
                device_instance.data.update_data(payload)
                
                # Daten aus dem DataHolder extrahieren
                if hasattr(device_instance.data, '_data') and device_instance.data._data:
                    result["params"] = dict(device_instance.data._data)
                    result["decoding_success"] = True
                    _LOGGER.info(f"✅ Device DataHolder successful: {len(result['params'])} parameters")
                else:
                    _LOGGER.debug(f"Device DataHolder returned no data")
                    result["decoding_success"] = False
            else:
                _LOGGER.warning(f"Device instance {device_type} has no known decoding method")
                result["decoding_success"] = False
            
            return result
            
        except Exception as e:
            _LOGGER.error(f"❌ Device class decoding failed for {device_type}: {e}")
            return {
                "device_sn": device_sn,
                "device_type": device_type,
                "timestamp": time.time(),
                "decoding_success": False,
                "error": str(e),
                "params": {}
            }

    def extract_important_parameters(self, params: dict) -> list:
        """Extrahiert wichtige Parameter für Logging"""
        important = []
        
        # Battery/SOC Parameter
        for key in ["battery_soc", "soc", "battery_percentage", "f32ShowSoc", "bmsBattSoc", "bms_bmsStatus.soc"]:
            if key in params and isinstance(params[key], (int, float)):
                important.append(f"{key}={params[key]}%")
        
        # Power Parameter
        power_keys = [k for k in params.keys() if any(term in k.lower() for term in ["power", "watt", "inputwatts", "outputwatts"])]
        for key in power_keys[:3]:  # Nur die ersten 3
            if isinstance(params[key], (int, float)):
                important.append(f"{key}={params[key]}W")
        
        # Cycle Parameter
        for key in ["cycles", "battery_cycles"]:
            if key in params and isinstance(params[key], (int, float)):
                important.append(f"{key}={params[key]}")
        
        # Temperature Parameter  
        temp_keys = [k for k in params.keys() if "temp" in k.lower()]
        for key in temp_keys[:2]:  # Nur die ersten 2
            if isinstance(params[key], (int, float)):
                important.append(f"{key}={params[key]}°C")
        
        return important[:5]  # Maximal 5 wichtige Parameter

    def publish_parameter_topics(self, device_sn: str, device_type: str, params: dict):
        """Publiziert einzelne Parameter auf separaten MQTT Topics"""
        try:
            # Nur für wichtige Parameter separate Topics erstellen
            important_params = {
                "battery_soc": ["battery_soc", "soc", "battery_percentage", "f32ShowSoc"],
                "power_in": ["inputWatts", "pd.wattsInSum", "inv.inputWatts", "mppt.inWatts"],
                "power_out": ["outputWatts", "pd.wattsOutSum", "inv.outputWatts", "mppt.outWatts"],
                "battery_cycles": ["cycles", "battery_cycles"],
                "temperature": ["temp", "battery_temp", "maxCellTemp"],
                "voltage": ["voltage", "vol", "battery_voltage"]
            }
            
            for param_type, possible_keys in important_params.items():
                for key in possible_keys:
                    if key in params and isinstance(params[key], (int, float)):
                        topic = f"{self.mqtt_base_topic}/{device_sn}/{param_type}"
                        value = params[key]
                        
                        # Einfaches JSON mit Wert und Zeitstempel
                        data = {
                            "value": value,
                            "timestamp": time.time(),
                            "unit": self.get_parameter_unit(param_type)
                        }
                        
                        self.mqtt_client.publish(topic, json.dumps(data), retain=True)
                        break  # Nur den ersten gefundenen Parameter verwenden
                        
        except Exception as e:
            _LOGGER.debug(f"Error publishing parameter topics: {e}")

    def publish_all_parameters(self, device_sn: str, device_type: str, params: dict, timestamp: float):
        """Publiziert ALLE Parameter auf separate MQTT Topics - nur der reine Wert"""
        try:
            for param_name, param_value in params.items():
                if param_name in ["error", "raw_hex", "raw_length"]:
                    # Fehler-Parameter auf separates Topic
                    topic = f"{self.mqtt_base_topic}/{device_sn}/errors/{param_name}"
                else:
                    # Normale Parameter auf eigenes Topic
                    topic = f"{self.mqtt_base_topic}/{device_sn}/{param_name}"
                
                # Parameter-Wert zu JSON-kompatiblem Format konvertieren
                json_compatible_value = self.convert_to_json_compatible(param_value)
                
                # Nur den reinen Wert publizieren (ohne Metadaten)
                try:
                    # Für einfache Werte: direkt als String oder Zahl publizieren
                    if isinstance(json_compatible_value, (int, float)):
                        payload = str(json_compatible_value)
                    elif isinstance(json_compatible_value, bool):
                        payload = "true" if json_compatible_value else "false"
                    elif isinstance(json_compatible_value, str):
                        payload = json_compatible_value
                    elif json_compatible_value is None:
                        payload = "null"
                    else:
                        # Für komplexe Objekte: als JSON publizieren
                        payload = json.dumps(json_compatible_value, ensure_ascii=False, default=str)
                    
                    self.mqtt_client.publish(topic, payload, retain=True)
                    
                except (TypeError, ValueError) as json_error:
                    # Fallback: String-Konvertierung
                    payload = str(json_compatible_value)
                    self.mqtt_client.publish(topic, payload, retain=True)
                    _LOGGER.debug(f"Used string fallback for parameter {param_name}: {json_error}")
                
            _LOGGER.debug(f"Published {len(params)} individual parameters for {device_sn}")
                        
        except Exception as e:
            _LOGGER.error(f"Error publishing all parameters: {e}")
            import traceback
            _LOGGER.error(traceback.format_exc())

    def convert_to_json_compatible(self, value):
        """Konvertiert beliebige Python-Objekte zu JSON-kompatiblen Formaten"""
        try:
            # Primitive Typen sind bereits JSON-kompatibel
            if value is None or isinstance(value, (bool, int, float, str)):
                return value
            
            # Listen und Tuples rekursiv konvertieren
            elif isinstance(value, (list, tuple)):
                return [self.convert_to_json_compatible(item) for item in value]
            
            # Dictionaries rekursiv konvertieren
            elif isinstance(value, dict):
                return {str(k): self.convert_to_json_compatible(v) for k, v in value.items()}
            
            # Bytes zu Hex-String
            elif isinstance(value, bytes):
                return value.hex()
            
            # Protobuf-Objekte (haben DESCRIPTOR Attribut)
            elif hasattr(value, 'DESCRIPTOR'):
                result = {}
                result["_protobuf_type"] = type(value).__name__
                
                # Alle Felder des Protobuf-Objekts extrahieren
                for field in value.DESCRIPTOR.fields:
                    try:
                        if value.HasField(field.name):
                            field_value = getattr(value, field.name)
                            result[field.name] = self.convert_to_json_compatible(field_value)
                    except Exception as field_error:
                        result[field.name] = f"<extraction_error: {field_error}>"
                
                return result
            
            # Enum-Werte
            elif hasattr(value, 'name') and hasattr(value, 'value'):
                return {
                    "_enum_type": type(value).__name__,
                    "name": value.name,
                    "value": value.value
                }
            
            # Datetime-Objekte
            elif hasattr(value, 'isoformat'):
                return value.isoformat()
            
            # Andere Objekte mit __dict__
            elif hasattr(value, '__dict__'):
                result = {
                    "_object_type": type(value).__name__,
                    "_module": getattr(type(value), '__module__', 'unknown')
                }
                # Versuche alle Attribute zu extrahieren
                for attr_name in dir(value):
                    if not attr_name.startswith('_'):
                        try:
                            attr_value = getattr(value, attr_name)
                            if not callable(attr_value):
                                result[attr_name] = self.convert_to_json_compatible(attr_value)
                        except Exception:
                            continue
                return result
            
            # Fallback: String-Konvertierung
            else:
                return {
                    "_fallback_string": str(value),
                    "_original_type": type(value).__name__
                }
                
        except Exception as e:
            # Absoluter Fallback
            return {
                "_conversion_error": str(e),
                "_original_value": str(value) if value is not None else None,
                "_original_type": type(value).__name__ if value is not None else "NoneType"
            }

    def get_parameter_unit_extended(self, param_name: str) -> str:
        """Erweiterte Einheiten-Erkennung basierend auf Parameter-Namen"""
        # Power-related parameters
        if any(keyword in param_name.lower() for keyword in ["power", "watt", "gridconnection"]):
            return "W"
        
        # SOC/Battery percentage
        if any(keyword in param_name.lower() for keyword in ["soc", "battery_percentage", "showsoc"]):
            return "%"
            
        # Voltage
        if any(keyword in param_name.lower() for keyword in ["vol", "voltage"]):
            return "V"
            
        # Current
        if any(keyword in param_name.lower() for keyword in ["current", "amp"]):
            return "A"
            
        # Temperature
        if any(keyword in param_name.lower() for keyword in ["temp", "temperature"]):
            return "°C"
            
        # Capacity
        if any(keyword in param_name.lower() for keyword in ["cap", "capacity"]):
            return "Ah"
            
        # Time (minutes/seconds)
        if any(keyword in param_name.lower() for keyword in ["time", "remaining"]):
            return "min"
            
        # Cycles
        if "cycle" in param_name.lower():
            return "cycles"
            
        return ""

    def get_parameter_unit(self, param_type: str) -> str:
        """Gibt die Einheit für Parameter-Typen zurück"""
        units = {
            "battery_soc": "%",
            "power_in": "W", 
            "power_out": "W",
            "battery_cycles": "cycles",
            "temperature": "°C",
            "voltage": "V"
        }
        return units.get(param_type, "")

    def detect_device_type(self, device_sn: str) -> str:
        """Automatische Erkennung des Gerätetyps basierend auf der Seriennummer"""
        # EcoFlow Seriennummer-Patterns (bekannte Prefixe)
        sn_patterns = {
            "BK11": "STREAM_ULTRA",   # Stream Ultra
            "BK21": "STREAM_AC",      # Stream AC
            "BK31": "STREAM_PRO",     # Stream Pro
            "HW52": "POWERSTREAM",    # PowerStream
            "R331": "DELTA_2",        # Delta 2
            "R351": "DELTA_2_MAX",    # Delta 2 Max
            "R711": "RIVER_2",        # River 2
            "R750": "RIVER_2_MAX",    # River 2 Max
            "R600": "RIVER_PRO",      # River Pro
            "R210": "RIVER_MAX",      # River Max
            "R211": "RIVER_MINI",     # River Mini
        }
        
        # Prüfe bekannte Patterns
        for prefix, device_type in sn_patterns.items():
            if device_sn.startswith(prefix):
                _LOGGER.info(f"Device type detected: {device_sn} -> {device_type}")
                return device_type
        
        # Fallback: Versuche aus SN-Struktur zu erraten
        if device_sn.startswith("BK"):
            _LOGGER.warning(f"Unknown Stream type for SN: {device_sn}, using STREAM_AC")
            return "STREAM_AC"
        elif device_sn.startswith("R"):
            _LOGGER.warning(f"Unknown River/Delta type for SN: {device_sn}, using DELTA_2")
            return "DELTA_2"
        elif device_sn.startswith("HW"):
            _LOGGER.warning(f"Unknown PowerStream type for SN: {device_sn}, using POWERSTREAM")
            return "POWERSTREAM"
        else:
            _LOGGER.warning(f"Completely unknown device type for SN: {device_sn}")
            return "UNKNOWN"

    def decode_stream_protobuf(self, payload: bytes) -> dict:
        """Dekodiert Stream AC/Ultra/Pro Protobuf-Daten"""
        try:
            # Direkte Stream-Dekodierung mit verbessertem Logging
            decoded = {"params": {}}
            
            try:
                # Versuche direkt mit EcoPacket
                from custom_components.ecoflow_cloud.devices.internal.proto import ecopacket_pb2
                
                # Versuche als Message (häufigster Stream-Typ)
                packet = ecopacket_pb2.Message()
                packet.ParseFromString(payload)
                
                _LOGGER.info(f"✅ EcoPacket Message parsing successful")
                
                decoded["protobuf_success"] = True
                decoded["message_type"] = "EcoPacketMessage"
                
                # Extrahiere Felder aus Message
                if hasattr(packet, 'cmd_func') and packet.HasField('cmd_func'):
                    decoded["params"]["cmd_func"] = packet.cmd_func
                    _LOGGER.info(f"� cmd_func: {packet.cmd_func}")
                
                if hasattr(packet, 'cmd_id') and packet.HasField('cmd_id'):
                    decoded["params"]["cmd_id"] = packet.cmd_id
                    _LOGGER.info(f"📝 cmd_id: {packet.cmd_id}")
                
                if hasattr(packet, 'device_sn') and packet.HasField('device_sn'):
                    decoded["params"]["device_sn"] = packet.device_sn
                    _LOGGER.info(f"📝 device_sn: {packet.device_sn}")
                
                # Wichtig: data Feld verarbeiten
                if hasattr(packet, 'data') and packet.HasField('data'):
                    data_field = packet.data
                    _LOGGER.info(f"🔍 EcoPacket data field found: {len(data_field)} bytes")
                    
                    # Versuche data als Stream-spezifischen Content zu dekodieren
                    stream_data = self.decode_stream_data_field(data_field)
                    if stream_data:
                        decoded["params"].update(stream_data)
                        _LOGGER.info(f"✅ Stream data decoded: {len(stream_data)} parameters")
                
                # Wenn wir Parameter gefunden haben, sind wir erfolgreich
                if len(decoded["params"]) > 0:
                    return decoded
                    
            except Exception as packet_error:
                _LOGGER.debug(f"EcoPacket Message parsing failed: {packet_error}")
            
            # Fallback: Versuche mit SendHeaderStreamMsg (ohne problematische Attribute)
            try:
                from custom_components.ecoflow_cloud.devices.internal.proto import stream_ac_pb2
                
                packet = stream_ac_pb2.SendHeaderStreamMsg()
                packet.ParseFromString(payload)
                
                _LOGGER.info(f"✅ SendHeaderStreamMsg parsing successful (fallback)")
                
                decoded["protobuf_success"] = True
                decoded["message_type"] = "SendHeaderStreamMsg"
                
                # Sichere Attribut-Zugriffe ohne problematische Felder
                if hasattr(packet, 'msg') and packet.msg:
                    _LOGGER.info(f"🔍 SendHeaderStreamMsg.msg found")
                    
                    # Nur sichere Felder verwenden
                    for field_name in ['cmd_id', 'src', 'dest', 'check_num', 'seq', 'version']:
                        if hasattr(packet.msg, field_name):
                            try:
                                if packet.msg.HasField(field_name):
                                    value = getattr(packet.msg, field_name)
                                    decoded["params"][field_name] = value
                                    _LOGGER.debug(f"📝 {field_name}: {value}")
                            except Exception:
                                continue
                    
                    # Verarbeite pdata wenn vorhanden
                    if hasattr(packet.msg, "pdata") and packet.msg.pdata and len(packet.msg.pdata) > 0:
                        pdata = packet.msg.pdata
                        _LOGGER.info(f"🔍 Stream pdata found: {len(pdata)} bytes")
                        
                        # Versuche pdata zu dekodieren
                        pdata_decoded = self.decode_stream_data_field(pdata)
                        if pdata_decoded:
                            decoded["params"].update(pdata_decoded)
                        
                        decoded["params"]["pdata_length"] = len(pdata)
                        decoded["params"]["pdata_hex"] = pdata.hex()[:100] + "..." if len(pdata.hex()) > 100 else pdata.hex()
                
                # Wenn wir Parameter gefunden haben, sind wir erfolgreich
                if len(decoded["params"]) > 0:
                    return decoded
                    
            except Exception as stream_error:
                _LOGGER.debug(f"SendHeaderStreamMsg parsing failed: {stream_error}")
            
            # Fallback: Intelligente Hex-Analyse mit Parameter-Extraktion
            decoded = {
                "protobuf_success": False,
                "message_type": "IntelligentHexAnalysis",
                "params": self.extract_stream_parameters_from_hex(payload)
            }
            
            _LOGGER.info(f"Stream intelligent hex analysis: {len(payload)} bytes -> {len(decoded['params'])} parameters")
            return decoded
            
        except Exception as e:
            _LOGGER.error(f"Stream protobuf decoding completely failed: {e}")
            # Minimaler Fallback
            return {
                "protobuf_success": False,
                "message_type": "Error",
                "error": str(e),
                "params": {
                    "raw_hex": payload.hex() if payload else "",
                    "raw_length": len(payload) if payload else 0
                }
            }

    def decode_stream_data_field(self, data_field: bytes) -> dict:
        """Dekodiert das data-Feld für Stream-Geräte - vollständige stream_ac.py Logik"""
        try:
            result = {}
            
            if len(data_field) == 0:
                return result
            
            # Komplette Integration der stream_ac.py _parsedata Logik
            from custom_components.ecoflow_cloud.devices.internal.proto import stream_ac_pb2
            
            _LOGGER.debug(f"Parsing Stream data field: {len(data_field)} bytes")
            
            # Liste der Stream-Message-Typen genau wie in stream_ac.py
            stream_types = [
                ("HeaderStream", stream_ac_pb2.HeaderStream),
                ("Champ_cmd21", stream_ac_pb2.Champ_cmd21), 
                ("Champ_cmd21_3", stream_ac_pb2.Champ_cmd21_3),
                ("Champ_cmd50", stream_ac_pb2.Champ_cmd50),
                ("Champ_cmd50_3", stream_ac_pb2.Champ_cmd50_3)
            ]
            
            success_count = 0
            
            for stream_name, stream_class in stream_types:
                try:
                    content = stream_class()
                    content.ParseFromString(data_field)
                    
                    # Prüfe ob wirklicher Inhalt vorhanden ist (wie in Original)
                    content_str = str(content)
                    if len(content_str) > 0 and content_str.strip():
                        _LOGGER.info(f"✅ Successfully parsed {stream_name}")
                        success_count += 1
                        
                        # Extrahiere alle Felder mit genau der gleichen Logik wie stream_ac.py
                        field_count = 0
                        for descriptor in content.DESCRIPTOR.fields:
                            try:
                                if not content.HasField(descriptor.name):
                                    continue
                                
                                value = getattr(content, descriptor.name)
                                field_name = descriptor.name
                                field_count += 1
                                
                                # Exakte Parameter-Verarbeitung wie in stream_ac.py
                                if field_name == "f32ShowSoc":
                                    result["battery_soc"] = round(value, 2)
                                    result["f32ShowSoc"] = value
                                    _LOGGER.info(f"🔋 Battery SOC: {result['battery_soc']}%")
                                elif field_name == "bmsBattSoc":
                                    result["bms_battery_soc"] = round(value, 2)  
                                    result["bmsBattSoc"] = value
                                    _LOGGER.info(f"🔋 BMS Battery SOC: {result['bms_battery_soc']}%")
                                elif field_name == "soc":
                                    result["soc"] = value
                                    result["battery_percentage"] = value
                                    _LOGGER.info(f"🔋 SOC: {value}%")
                                elif field_name in ["bmsChgRemTime", "bmsDsgRemTime"]:
                                    result[field_name] = value
                                    if field_name == "bmsChgRemTime":
                                        result["charge_remaining_minutes"] = value
                                        _LOGGER.info(f"⏱️ Charge remaining: {value} min")
                                    elif field_name == "bmsDsgRemTime":
                                        result["discharge_remaining_minutes"] = value
                                        _LOGGER.info(f"⏱️ Discharge remaining: {value} min")
                                elif field_name == "cycles":
                                    result["battery_cycles"] = value
                                    result["cycles"] = value
                                    _LOGGER.info(f"🔄 Battery cycles: {value}")
                                elif field_name in ["designCap", "fullCap", "remainCap"]:
                                    result[field_name] = value
                                    _LOGGER.info(f"🔋 {field_name}: {value}")
                                elif field_name in ["gridConnectionPower", "inputWatts", "outputWatts"]:
                                    result[field_name] = round(value, 2)
                                    _LOGGER.info(f"⚡ {field_name}: {result[field_name]}W")
                                elif field_name in ["powGetPvSum", "powGetBpCms", "powGetSysGrid"]:
                                    result[field_name] = round(value, 2)
                                    _LOGGER.info(f"⚡ {field_name}: {result[field_name]}W")
                                elif field_name in ["maxCellTemp", "minCellTemp", "temp"]:
                                    result[field_name] = value
                                    _LOGGER.debug(f"🌡️ {field_name}: {value}°C")
                                elif field_name in ["maxCellVol", "minCellVol", "vol"]:
                                    result[field_name] = value
                                    _LOGGER.debug(f"⚡ {field_name}: {value}V")
                                else:
                                    result[field_name] = value
                                    _LOGGER.debug(f"📊 {field_name}: {value}")
                                    
                            except Exception as field_error:
                                _LOGGER.debug(f"Failed to process field {descriptor.name}: {field_error}")
                                continue
                        
                        _LOGGER.info(f"📊 {stream_name}: extracted {field_count} fields")
                        
                        # Wenn wir wichtige Parameter gefunden haben, können wir früh zurückkehren
                        if any(key in result for key in ["battery_soc", "soc", "battery_percentage"]):
                            _LOGGER.info(f"✅ Found key battery parameters in {stream_name}")
                            break
                
                except Exception as e:
                    _LOGGER.debug(f"Failed to parse {stream_name}: {e}")
                    continue
            
            if success_count > 0:
                _LOGGER.info(f"✅ Stream data parsing successful: {success_count} message types parsed, {len(result)} total parameters")
                
                # Log wichtige gefundene Parameter
                key_params = []
                if "battery_soc" in result:
                    key_params.append(f"battery_soc={result['battery_soc']}%")
                if "soc" in result:
                    key_params.append(f"soc={result['soc']}%")
                if "battery_cycles" in result:
                    key_params.append(f"cycles={result['battery_cycles']}")
                
                power_params = [k for k in result.keys() if 'power' in k.lower() or 'watt' in k.lower()]
                if power_params:
                    key_params.append(f"power_fields={len(power_params)}")
                
                if key_params:
                    _LOGGER.info(f"🎯 Key parameters: {', '.join(key_params)}")
                
                return result
            else:
                _LOGGER.debug(f"No Stream message types successfully parsed from {len(data_field)} bytes")
                return {}
                
        except ImportError as e:
            _LOGGER.error(f"Cannot import stream_ac_pb2: {e}")
            return {}
        except Exception as e:
            _LOGGER.debug(f"Stream data field decoding failed: {e}")
            return {}

    def extract_stream_parameters_from_hex(self, payload: bytes) -> dict:
        """Extrahiert Stream-Parameter durch intelligente Hex-Analyse"""
        try:
            result = {}
            
            if len(payload) < 4:
                return {"raw_hex": payload.hex(), "raw_length": len(payload)}
            
            # Analysiere Protobuf-Struktur
            hex_str = payload.hex()
            result["raw_hex"] = hex_str[:100] + "..." if len(hex_str) > 100 else hex_str
            result["raw_length"] = len(payload)
            
            # Suche nach typischen Stream-Parametern in verschiedenen Datenformaten
            import struct
            
            # Float-Werte suchen (32-bit IEEE 754)
            float_candidates = []
            for i in range(len(payload) - 3):
                try:
                    float_val = struct.unpack('<f', payload[i:i+4])[0]  # Little-endian
                    if 0 <= float_val <= 200 and float_val != 0:  # Plausible Werte
                        float_candidates.append((i, float_val))
                except:
                    continue
            
            # Integer-Werte suchen (16-bit und 32-bit)
            int16_candidates = []
            int32_candidates = []
            
            for i in range(len(payload) - 1):
                try:
                    val16 = struct.unpack('<H', payload[i:i+2])[0]  # Unsigned 16-bit
                    if 0 <= val16 <= 65000:
                        int16_candidates.append((i, val16))
                except:
                    continue
            
            for i in range(len(payload) - 3):
                try:
                    val32 = struct.unpack('<I', payload[i:i+4])[0]  # Unsigned 32-bit
                    if 0 <= val32 <= 1000000:
                        int32_candidates.append((i, val32))
                except:
                    continue
            
            # Interpretiere die besten Kandidaten
            param_count = 0
            
            # Float-Werte als potentielle SOC/Power-Werte
            for offset, value in float_candidates[:5]:  # Top 5
                if 0 < value <= 100:
                    result[f"float_param_{param_count}_soc_candidate"] = round(value, 2)
                    param_count += 1
                elif 0 < value <= 10000:
                    result[f"float_param_{param_count}_power_candidate"] = round(value, 1)
                    param_count += 1
            
            # Integer-Werte als potentielle Status/Counter
            for offset, value in int16_candidates[:3]:  # Top 3
                if 0 < value <= 1000:
                    result[f"int16_param_{param_count}"] = value
                    param_count += 1
            
            for offset, value in int32_candidates[:2]:  # Top 2
                if 0 < value <= 100000:
                    result[f"int32_param_{param_count}"] = value
                    param_count += 1
            
            # Spezielle Stream Ultra Patterns
            if len(payload) >= 20:
                # Suche nach typischen Stream-Sequenzen
                if b'\x08\x10' in payload or b'\x10\x18' in payload:
                    result["stream_pattern_detected"] = True
                
                # Zeitstempel-ähnliche Patterns
                for i in range(len(payload) - 7):
                    try:
                        timestamp_candidate = struct.unpack('<Q', payload[i:i+8])[0]
                        if 1600000000 <= timestamp_candidate <= 2000000000:  # Plausible Unix-Timestamps
                            result["timestamp_candidate"] = timestamp_candidate
                            break
                    except:
                        continue
            
            _LOGGER.debug(f"Extracted {param_count} parameters from hex analysis")
            return result
            
        except Exception as e:
            _LOGGER.debug(f"Hex parameter extraction failed: {e}")
            return {"raw_hex": payload.hex() if payload else "", "raw_length": len(payload) if payload else 0}

    def _process_stream_field_safe(self, result: dict, field_name: str, value):
        """Verarbeitet Stream-Felder sicher ohne Exceptions"""
        try:
            # Wichtige Stream-Parameter mit bekannten Namen
            if field_name in ["soc", "battery_soc", "f32ShowSoc", "bmsBattSoc"]:
                if isinstance(value, (int, float)) and 0 <= value <= 100:
                    result["battery_soc"] = round(float(value), 2)
                    result[field_name] = value
            elif field_name in ["watts", "power", "gridPower", "ac_power", "dc_power"]:
                if isinstance(value, (int, float)):
                    result["power_watts"] = round(float(value), 1)
                    result[field_name] = value
            elif field_name in ["voltage", "vol", "battery_voltage"]:
                if isinstance(value, (int, float)) and 0 <= value <= 1000:
                    result["voltage"] = round(float(value), 2)
                    result[field_name] = value
            elif field_name in ["current", "amp", "battery_current"]:
                if isinstance(value, (int, float)):
                    result["current"] = round(float(value), 2)
                    result[field_name] = value
            elif field_name in ["temp", "temperature", "battery_temp"]:
                if isinstance(value, (int, float)) and -50 <= value <= 100:
                    result["temperature"] = round(float(value), 1)
                    result[field_name] = value
            elif field_name in ["cycles", "charge_cycles"]:
                if isinstance(value, int) and 0 <= value <= 10000:
                    result["battery_cycles"] = value
                    result[field_name] = value
            else:
                # Generische Behandlung
                converted_value = self.convert_protobuf_value(value)
                if converted_value is not None:
                    result[field_name] = converted_value
                    
        except Exception as e:
            _LOGGER.debug(f"Error processing stream field {field_name}: {e}")
            # Fallback: String-Konvertierung
            try:
                result[field_name] = str(value)
            except:
                pass

    def _analyze_hex_data(self, payload: bytes) -> dict:
        """Analysiert Hex-Daten um mögliche Informationen zu extrahieren"""
        try:
            analysis = {
                "length": len(payload),
                "first_bytes": payload[:8].hex() if len(payload) >= 8 else payload.hex(),
                "last_bytes": payload[-8:].hex() if len(payload) >= 8 else "",
            }
            
            # Suche nach bekannten Patterns
            hex_str = payload.hex()
            
            # Stream-typische Patterns
            if "0a" in hex_str[:20]:  # Protobuf field markers
                analysis["protobuf_detected"] = True
            
            # Versuche Float-Werte zu finden (SOC könnte als Float kodiert sein)
            if len(payload) >= 4:
                import struct
                for i in range(len(payload) - 3):
                    try:
                        float_val = struct.unpack('f', payload[i:i+4])[0]
                        if 0 <= float_val <= 100:  # Möglicher SOC-Wert
                            analysis[f"possible_soc_at_offset_{i}"] = round(float_val, 2)
                    except:
                        continue
            
            return analysis
            
        except Exception as e:
            return {"error": str(e)}

    def decode_delta2_protobuf(self, payload: bytes) -> dict:
        """Dekodiert Delta 2 Protobuf-Daten"""
        try:
            from custom_components.ecoflow_cloud.devices.internal.proto import ecopacket_pb2
            
            packet = ecopacket_pb2.Header()
            packet.ParseFromString(payload)
            
            decoded = {"params": {}, "protobuf_success": True}
            for field in packet.DESCRIPTOR.fields:
                if packet.HasField(field.name):
                    value = getattr(packet, field.name)
                    decoded["params"][field.name] = self.convert_protobuf_value(value)
            
            return decoded
            
        except Exception as e:
            _LOGGER.debug(f"Delta2 protobuf decoding failed: {e}")
            return self.decode_generic_protobuf(payload)

    def decode_powerstream_protobuf(self, payload: bytes) -> dict:
        """Dekodiert PowerStream Protobuf-Daten"""
        try:
            from custom_components.ecoflow_cloud.devices.internal.proto import powerstream_pb2
            
            # Versuche PowerStream-spezifische Nachrichten
            decoded = {"params": {}, "protobuf_success": True}
            
            # Hier könnten PowerStream-spezifische Nachrichten-Typen hinzugefügt werden
            # Fallback auf generische Dekodierung
            decoded.update(self.decode_generic_protobuf(payload))
            
            return decoded
            
        except Exception as e:
            _LOGGER.debug(f"PowerStream protobuf decoding failed: {e}")
            return self.decode_generic_protobuf(payload)

    def decode_river_protobuf(self, payload: bytes) -> dict:
        """Dekodiert River Protobuf-Daten"""
        try:
            from custom_components.ecoflow_cloud.devices.internal.proto import ecopacket_pb2
            
            packet = ecopacket_pb2.Header()
            packet.ParseFromString(payload)
            
            decoded = {"params": {}, "protobuf_success": True}
            for field in packet.DESCRIPTOR.fields:
                if packet.HasField(field.name):
                    value = getattr(packet, field.name)
                    decoded["params"][field.name] = self.convert_protobuf_value(value)
            
            return decoded
            
        except Exception as e:
            _LOGGER.debug(f"River protobuf decoding failed: {e}")
            return self.decode_generic_protobuf(payload)

    def decode_generic_protobuf(self, payload: bytes) -> dict:
        """Generische Protobuf-Dekodierung für alle Geräte"""
        try:
            from custom_components.ecoflow_cloud.devices.internal.proto import ecopacket_pb2
            
            decoded = {"params": {}}
            
            # Versuche als Header
            try:
                packet = ecopacket_pb2.Header()
                packet.ParseFromString(payload)
                
                decoded["protobuf_success"] = True
                decoded["message_type"] = "Header"
                
                for field in packet.DESCRIPTOR.fields:
                    if packet.HasField(field.name):
                        value = getattr(packet, field.name)
                        key = field.name
                        
                        # Spezielle Behandlung für wichtige Felder
                        if key == "pdata" and isinstance(value, bytes):
                            # Versuche pdata zu dekodieren
                            pdata_decoded = self.decode_pdata_content(value)
                            if pdata_decoded:
                                decoded["params"].update(pdata_decoded)
                            decoded["params"]["pdata_hex"] = value.hex()
                            decoded["params"]["pdata_length"] = len(value)
                        else:
                            decoded["params"][key] = self.convert_protobuf_value(value)
                
                return decoded
                
            except Exception:
                pass
            
            # Versuche als SendMsgHart
            try:
                msg_hart = ecopacket_pb2.SendMsgHart()
                msg_hart.ParseFromString(payload)
                
                decoded["protobuf_success"] = True
                decoded["message_type"] = "SendMsgHart"
                
                for field in msg_hart.DESCRIPTOR.fields:
                    if msg_hart.HasField(field.name):
                        value = getattr(msg_hart, field.name)
                        decoded["params"][field.name] = self.convert_protobuf_value(value)
                
                return decoded
                
            except Exception:
                pass
            
            # Wenn alle Versuche fehlschlagen
            decoded["protobuf_success"] = False
            decoded["message_type"] = "Unknown"
            return decoded
            
        except Exception as e:
            _LOGGER.debug(f"Generic protobuf decoding failed: {e}")
            return {"protobuf_success": False, "params": {}}

    def decode_pdata_content(self, pdata: bytes) -> dict:
        """Versucht den Inhalt von pdata zu dekodieren"""
        try:
            # Versuche verschiedene bekannte Strukturen
            result = {}
            
            # Einfache Hex-Analyse für bekannte Patterns
            hex_data = pdata.hex()
            
            # Stream-spezifische Patterns
            if len(pdata) > 50:  # Stream-Daten sind typischerweise länger
                # Einfache Hex-Analyse statt problematischer Protobuf-Dekodierung
                result.update(self._analyze_hex_data(pdata))
            
            return result
            
        except Exception as e:
            _LOGGER.debug(f"pdata decoding failed: {e}")
            return {}

    def convert_protobuf_value(self, value):
        """Konvertiert Protobuf-Werte zu JSON-kompatiblen Typen"""
        if isinstance(value, bytes):
            # Versuche als UTF-8 String, sonst als Hex
            try:
                decoded_str = value.decode('utf-8')
                # Prüfe ob es sinnvoller Text ist
                if all(ord(c) < 128 and (c.isprintable() or c.isspace()) for c in decoded_str):
                    return decoded_str
                else:
                    return value.hex()
            except:
                return value.hex()
        elif hasattr(value, 'DESCRIPTOR'):  # Nested message
            result = {}
            for field in value.DESCRIPTOR.fields:
                if value.HasField(field.name):
                    field_value = getattr(value, field.name)
                    result[field.name] = self.convert_protobuf_value(field_value)
            return result
        elif isinstance(value, (list, tuple)):
            return [self.convert_protobuf_value(item) for item in value]
        elif isinstance(value, float):
            # Runde Float-Werte für bessere Lesbarkeit
            return round(value, 3)
        else:
            return value

    async def start(self):
        """Startet den EcoFlow MQTT Publisher"""
        _LOGGER.info("EcoFlow MQTT Publisher starting...")
        
        try:
            # MQTT Client setup
            self.setup_mqtt_client()
            
            # EcoFlow API Client setup
            await self.setup_api_client()
            
            # Message Forwarding setup
            self.setup_ecoflow_message_forwarding()
            
            # Kurz warten für die EcoFlow MQTT-Verbindung
            _LOGGER.info("⏳ Waiting for EcoFlow MQTT connection...")
            await asyncio.sleep(5)
            
            # Verbindungsstatus nochmals prüfen
            if hasattr(self.api_client, 'mqtt_client') and self.api_client.mqtt_client:
                ecoflow_paho_client = None
                if hasattr(self.api_client.mqtt_client, '_EcoflowMQTTClient__client'):
                    ecoflow_paho_client = self.api_client.mqtt_client._EcoflowMQTTClient__client
                elif hasattr(self.api_client.mqtt_client, '__client'):
                    ecoflow_paho_client = self.api_client.mqtt_client.__client
                
                if ecoflow_paho_client:
                    connected = ecoflow_paho_client.is_connected()
                    _LOGGER.info(f"🔍 EcoFlow MQTT final status: Connected={connected}")
                    if not connected:
                        _LOGGER.warning("⚠️ EcoFlow MQTT not yet connected - messages may arrive delayed")
                    else:
                        _LOGGER.info("✅ EcoFlow MQTT fully connected and ready")
            
            # Nachrichten-Zähler für Debugging
            self.message_count = 0
            self.last_message_time = None
            
            # Hauptschleife starten
            self.running = True
            status_counter = 0
            while self.running:
                status_counter += 1
                
                # Status-Update senden
                message_stats = {
                    'total_messages': getattr(self, 'message_count', 0),
                    'last_message_time': getattr(self, 'last_message_time', None),
                    'seconds_since_last_message': time.time() - getattr(self, 'last_message_time', time.time()) if getattr(self, 'last_message_time', None) else None
                }
                
                status = {
                    'status': 'running',
                    'timestamp': time.time(),
                    'devices': self.device_sns,
                    'messages': message_stats,
                    'status_update_count': status_counter
                }
                
                self.mqtt_client.publish(
                    f"{self.mqtt_base_topic}/status", 
                    json.dumps(status), 
                    retain=True
                )
                
                # Status für jedes Gerät senden
                for device_sn in self.device_sns:
                    device_status = {
                        'device_sn': device_sn,
                        'timestamp': time.time(),
                        'status': 'connected'
                    }
                    topic = f"{self.mqtt_base_topic}/{device_sn}/status"
                    self.mqtt_client.publish(topic, json.dumps(device_status), retain=True)
                
                # Logging mit Nachrichten-Info
                msg_info = f"📊 Messages so far: {getattr(self, 'message_count', 0)}"
                if getattr(self, 'last_message_time', None):
                    seconds_ago = int(time.time() - self.last_message_time)
                    msg_info += f", last {seconds_ago}s ago"
                else:
                    msg_info += ", none received yet"
                
                _LOGGER.info(f"Status sent for {len(self.device_sns)} devices - {msg_info}")
                await asyncio.sleep(60)
                
        except Exception as e:
            _LOGGER.error(f"Error during startup: {e}")
            raise

    def stop(self):
        """Stoppt den Publisher"""
        _LOGGER.info("EcoFlow MQTT Publisher stopping...")
        self.running = False
        
        if self.api_client:
            self.api_client.stop()
            
        if self.mqtt_client:
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()


def signal_handler(signum, frame):
    """Signal Handler für graceful shutdown"""
    _LOGGER.info(f"Signal {signum} received, shutting down...")
    if hasattr(signal_handler, 'publisher'):
        signal_handler.publisher.stop()
    sys.exit(0)


async def main():
    """Hauptfunktion"""
    # Signal Handler registrieren
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        publisher = EcoflowMqttPublisher()
        signal_handler.publisher = publisher  # Für Signal Handler verfügbar machen
        await publisher.start()
    except Exception as e:
        _LOGGER.error(f"Error during startup: {e}")
        _LOGGER.error("Full traceback:", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
