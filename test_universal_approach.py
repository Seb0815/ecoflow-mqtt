#!/usr/bin/env python3
"""
EcoFlow Universal Test - Kombiniert Device-Klassen mit universellem Ansatz
Testet den universellen JSON-Parsing Ansatz vom ecoflow_exporter
"""

import json
import logging
import time
import os
import asyncio
from typing import Dict, Set

# EcoFlow Imports 
from custom_components.ecoflow_cloud.api.private_api import EcoflowPrivateApiClient

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
_LOGGER = logging.getLogger(__name__)

class UniversalEcoflowTest:
    """Universeller Test-Ansatz basierend auf ecoflow_exporter"""
    
    def __init__(self):
        self.api_client = None
        self.message_count = 0
        self.discovered_parameters = {}  # device_sn -> set of parameters
        self.parameter_values = {}      # device_sn -> latest values
        self.load_config()

    def load_config(self):
        """Lädt Konfiguration aus Umgebungsvariablen"""
        self.username = os.getenv("ECOFLOW_USERNAME")
        self.password = os.getenv("ECOFLOW_PASSWORD")
        
        if not self.username or not self.password:
            raise ValueError("ECOFLOW_USERNAME und ECOFLOW_PASSWORD müssen gesetzt sein")
        
        # Device Liste
        self.device_sns = [sn.strip() for sn in os.getenv("ECOFLOW_DEVICES", "").split(",") if sn.strip()]
        _LOGGER.info(f"Testing devices: {self.device_sns}")

    async def setup_api_client(self):
        """Erstellt EcoFlow API Client"""
        self.api_client = EcoflowPrivateApiClient(
            "api.ecoflow.com",
            self.username,
            self.password,
            "v1"
        )
        
        self.api_client.device_sns = self.device_sns
        await self.api_client.login()
        _LOGGER.info("Successfully logged in to EcoFlow API")
        
        # MQTT Message Handler setup
        self.setup_universal_message_handler()
        
        # Start MQTT
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self.api_client.start)
        _LOGGER.info("EcoFlow MQTT Client started")

    def setup_universal_message_handler(self):
        """Setup universeller Message Handler nach ecoflow_exporter Vorbild"""
        if hasattr(self.api_client, 'mqtt_client') and self.api_client.mqtt_client:
            # Zugriff auf den inneren paho-mqtt Client
            ecoflow_paho_client = None
            if hasattr(self.api_client.mqtt_client, '_EcoflowMQTTClient__client'):
                ecoflow_paho_client = self.api_client.mqtt_client._EcoflowMQTTClient__client
            elif hasattr(self.api_client.mqtt_client, '__client'):
                ecoflow_paho_client = self.api_client.mqtt_client.__client
            
            if ecoflow_paho_client:
                # Ersetze Message Handler mit unserem universellen Ansatz
                ecoflow_paho_client.on_message = self.on_universal_ecoflow_message
                _LOGGER.info("Universal message handler installed")
            else:
                _LOGGER.error("Could not access EcoFlow paho MQTT client")

    def on_universal_ecoflow_message(self, client, userdata, message):
        """Universeller Message Handler - basiert auf ecoflow_exporter Ansatz"""
        try:
            self.message_count += 1
            topic = message.topic
            payload = message.payload
            
            _LOGGER.info(f"Universal Message #{self.message_count} - Topic: {topic}")
            
            # Extrahiere device_sn aus Topic
            device_sn = None
            for sn in self.device_sns:
                if sn in topic:
                    device_sn = sn
                    break
            
            if not device_sn:
                _LOGGER.warning(f"Could not extract device SN from topic: {topic}")
                return
            
            # 🎯 UNIVERSELLER ANSATZ: Versuche direktes JSON-Parsing (wie ecoflow_exporter)
            try:
                # Methode 1: Direktes JSON-Parsing (ecoflow_exporter Ansatz)
                payload_str = payload.decode('utf-8')
                json_data = json.loads(payload_str)
                
                if 'params' in json_data:
                    params = json_data['params']
                    _LOGGER.info(f"✅ UNIVERSAL JSON SUCCESS: Found {len(params)} parameters for {device_sn}")
                    self.process_universal_parameters(device_sn, params, "JSON_DIRECT")
                    return
                    
            except (json.JSONDecodeError, UnicodeDecodeError):
                _LOGGER.debug("Direct JSON parsing failed, trying Device-Class approach")
            
            # 🔧 FALLBACK: Device-Klassen Ansatz für Protobuf
            device_type = self.detect_device_type(device_sn)
            _LOGGER.info(f"Fallback to Device-Class approach for {device_type}")
            
            # Lade Device-Klasse
            device_class = self.get_device_class(device_type)
            if device_class:
                device_instance = device_class()
                
                # Verwende _prepare_data für Protobuf-Dekodierung
                if hasattr(device_instance, '_prepare_data'):
                    decoded_data = device_instance._prepare_data(payload)
                    if decoded_data and "params" in decoded_data:
                        params = decoded_data["params"]
                        _LOGGER.info(f"🔧 DEVICE-CLASS SUCCESS: Found {len(params)} parameters for {device_sn}")
                        self.process_universal_parameters(device_sn, params, "DEVICE_CLASS")
                        return
            
            _LOGGER.warning(f"Both universal JSON and Device-Class approach failed for {device_sn}")
            
        except Exception as e:
            _LOGGER.error(f"Universal message handler error: {e}")

    def process_universal_parameters(self, device_sn: str, params: dict, method: str):
        """Verarbeitet Parameter universal - nach ecoflow_exporter Vorbild"""
        try:
            # Initialisiere Sets falls noch nicht vorhanden
            if device_sn not in self.discovered_parameters:
                self.discovered_parameters[device_sn] = set()
                self.parameter_values[device_sn] = {}
            
            # Zähle neue vs. bekannte Parameter
            new_params = []
            updated_params = []
            
            for param_key, param_value in params.items():
                # Nur numerische Werte berücksichtigen (wie ecoflow_exporter)
                if not isinstance(param_value, (int, float)):
                    continue
                
                # Prüfe ob neuer Parameter
                if param_key not in self.discovered_parameters[device_sn]:
                    self.discovered_parameters[device_sn].add(param_key)
                    new_params.append((param_key, param_value))
                else:
                    updated_params.append((param_key, param_value))
                
                # Aktualisiere Wert
                self.parameter_values[device_sn][param_key] = param_value
            
            # Logging der Ergebnisse
            _LOGGER.info(f"=== UNIVERSAL PROCESSING RESULTS ({method}) ===")
            _LOGGER.info(f"Device: {device_sn}")
            _LOGGER.info(f"Total parameters: {len(params)}")
            _LOGGER.info(f"Numeric parameters: {len(new_params) + len(updated_params)}")
            _LOGGER.info(f"New parameters discovered: {len(new_params)}")
            _LOGGER.info(f"Updated parameters: {len(updated_params)}")
            
            # Zeige neue Parameter
            if new_params:
                _LOGGER.info("=== NEW PARAMETERS DISCOVERED ===")
                for param_key, param_value in new_params[:10]:  # Top 10
                    # Erkenne Einheit basierend auf Parametername
                    unit = self.guess_parameter_unit(param_key)
                    _LOGGER.info(f"🆕 {param_key} = {param_value}{unit}")
                
                if len(new_params) > 10:
                    _LOGGER.info(f"... and {len(new_params)-10} more new parameters")
            
            # Zeige interessante aktualisierte Werte
            interesting_updates = [
                (k, v) for k, v in updated_params 
                if any(keyword in k.lower() for keyword in ["soc", "power", "watt", "temp", "vol"])
            ]
            
            if interesting_updates:
                _LOGGER.info("=== INTERESTING UPDATES ===")
                for param_key, param_value in interesting_updates[:5]:  # Top 5
                    unit = self.guess_parameter_unit(param_key)
                    _LOGGER.info(f"🔄 {param_key} = {param_value}{unit}")
            
            # Gesamt-Statistik
            total_discovered = len(self.discovered_parameters[device_sn])
            _LOGGER.info(f"Total discovered parameters for {device_sn}: {total_discovered}")
            
        except Exception as e:
            _LOGGER.error(f"Error processing universal parameters: {e}")

    def guess_parameter_unit(self, param_name: str) -> str:
        """Ratet die Einheit basierend auf Parametername - nach ecoflow_exporter Vorbild"""
        param_lower = param_name.lower()
        
        # Power
        if any(keyword in param_lower for keyword in ["power", "watt"]):
            return "W"
        
        # SOC/Percentage
        if any(keyword in param_lower for keyword in ["soc", "percentage"]):
            return "%"
        
        # Voltage (in mV usually)
        if any(keyword in param_lower for keyword in ["vol", "voltage"]):
            return "V"  # oder mV
        
        # Current
        if any(keyword in param_lower for keyword in ["amp", "current"]):
            return "A"
        
        # Temperature
        if "temp" in param_lower:
            return "°C"
        
        # Capacity
        if "cap" in param_lower:
            return "Ah"
        
        # Time
        if "time" in param_lower:
            return "min"
        
        return ""

    def detect_device_type(self, device_sn: str) -> str:
        """Automatische Gerätetyp-Erkennung"""
        sn_patterns = {
            "BK11": "STREAM_ULTRA",
            "BK21": "STREAM_AC", 
            "BK31": "STREAM_PRO",
            "HW52": "POWERSTREAM",
            "R331": "DELTA_2",
            "R351": "DELTA_2_MAX",
        }
        
        for prefix, device_type in sn_patterns.items():
            if device_sn.startswith(prefix):
                return device_type
        
        return "UNKNOWN"

    def get_device_class(self, device_type: str):
        """Lädt Device-Klasse"""
        device_map = {
            "STREAM_ULTRA": "stream_ac.StreamAC",
            "STREAM_AC": "stream_ac.StreamAC",
            "STREAM_PRO": "stream_ac.StreamAC", 
            "DELTA_2": "delta2.Delta2",
            "DELTA_2_MAX": "delta2_max.Delta2Max",
        }
        
        if device_type not in device_map:
            return None
        
        module_path, class_name = device_map[device_type].rsplit('.', 1)
        try:
            module = __import__(f"custom_components.ecoflow_cloud.devices.internal.{module_path}", fromlist=[class_name])
            return getattr(module, class_name)
        except Exception as e:
            _LOGGER.error(f"Failed to load {device_type}: {e}")
            return None

    async def run_test(self, duration_seconds=60):
        """Führt den Test für eine bestimmte Zeit aus"""
        _LOGGER.info(f"Starting universal test for {duration_seconds} seconds...")
        
        await self.setup_api_client()
        
        # Warte und sammle Daten
        await asyncio.sleep(duration_seconds)
        
        # Zeige finale Statistiken
        self.print_final_statistics()

    def print_final_statistics(self):
        """Zeigt finale Statistiken"""
        _LOGGER.info("=== FINAL UNIVERSAL TEST STATISTICS ===")
        _LOGGER.info(f"Total messages processed: {self.message_count}")
        
        for device_sn, params in self.discovered_parameters.items():
            _LOGGER.info(f"Device {device_sn}: {len(params)} unique parameters discovered")
            
            # Top Parameter nach Kategorien
            values = self.parameter_values.get(device_sn, {})
            
            power_params = [(k, v) for k, v in values.items() if "power" in k.lower() or "watt" in k.lower()]
            soc_params = [(k, v) for k, v in values.items() if "soc" in k.lower()]
            temp_params = [(k, v) for k, v in values.items() if "temp" in k.lower()]
            
            _LOGGER.info(f"  Power parameters: {len(power_params)}")
            _LOGGER.info(f"  SOC parameters: {len(soc_params)}")
            _LOGGER.info(f"  Temperature parameters: {len(temp_params)}")

async def main():
    """Hauptfunktion für den Universal-Test"""
    test = UniversalEcoflowTest()
    
    try:
        # Test für 2 Minuten
        await test.run_test(120)
    except KeyboardInterrupt:
        _LOGGER.info("Test interrupted by user")
    except Exception as e:
        _LOGGER.error(f"Test error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
