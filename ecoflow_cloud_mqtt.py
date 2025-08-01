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
import threading
import time
import traceback
import datetime
from typing import Dict  # Kept for compatibility

import paho.mqtt.client as mqtt

# EcoFlow API Imports
from custom_components.ecoflow_cloud.api.private_api import EcoflowPrivateApiClient
from custom_components.ecoflow_cloud.api.public_api import EcoflowPublicApiClient
from custom_components.ecoflow_cloud.device_data import DeviceData, DeviceOptions

# Logging Setup - konfigurierbar via LOG_LEVEL Umgebungsvariable
log_level_str = os.getenv("LOG_LEVEL", "INFO").upper()
log_level_map = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL
}
log_level = log_level_map.get(log_level_str, logging.INFO)

logging.basicConfig(
    level=log_level,
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
        self.defined_parameters_cache = {}  # Cache für definierte Parameter pro Device-Typ
        
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
        
        # MQTT Client starten (Python 3.13 kompatibel)
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self.api_client.start)
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
                
                # Lade definierte Parameter für Filterung
                defined_params = self.get_defined_parameters_for_device(device_instance, device_type)
                _LOGGER.info(f"Device {device_type} ({device_sn}): {len(defined_params)} defined parameters will be published via MQTT")
                
                _LOGGER.info(f"Created {device_type} device instance for {device_sn}")
                
            except Exception as e:
                _LOGGER.error(f"Failed to create device instance for {device_sn}: {e}")
                _LOGGER.error(f"Detailed error: {traceback.format_exc()}")
                # Fallback: Nutze DiagnosticDevice
                from custom_components.ecoflow_cloud.devices import DiagnosticDevice
                self.devices[device_sn] = None  # Placeholder
        
        _LOGGER.info(f"Created {len([d for d in self.devices.values() if d is not None])} device instances")

    def get_defined_parameters_for_device(self, device_instance, device_type: str) -> set:
        """Extrahiert alle in der Device-Klasse definierten Parameter durch direkte Analyse der Device-Klasse"""
        
        # Cache prüfen - Parameter nur einmal pro Device-Typ extrahieren
        if device_type in self.defined_parameters_cache:
            _LOGGER.debug(f"Using cached parameters for {device_type}: {len(self.defined_parameters_cache[device_type])} parameters")
            return self.defined_parameters_cache[device_type]
        
        defined_params = set()
        
        try:
            # Verwende die neue get_defined_parameters Methode der Device-Klasse falls verfügbar
            if hasattr(device_instance, 'get_defined_parameters') and callable(device_instance.get_defined_parameters):
                defined_params = device_instance.get_defined_parameters()
                _LOGGER.info(f"Used device class method: {len(defined_params)} parameters for {device_type}")
            
            # Fallback: Extrahiere Parameter aus sensors() Methode
            elif hasattr(device_instance, 'sensors') and callable(device_instance.sensors):
                try:
                    sensors = device_instance.sensors(None)  # Dummy client
                    
                    for sensor in sensors:
                        # Der dritte Parameter im Konstruktor ist der Parameter-Name
                        if hasattr(sensor, 'attr_key') and sensor.attr_key:
                            defined_params.add(sensor.attr_key)
                        elif hasattr(sensor, '_attr_key') and sensor._attr_key:
                            defined_params.add(sensor._attr_key)
                    
                    _LOGGER.info(f"Dynamically extracted {len(defined_params)} parameters for {device_type}")
                    
                except Exception as e:
                    _LOGGER.debug(f"Dynamic parameter extraction failed for {device_type}: {e}")
            
            # Letzter Fallback: Lade Device-Klasse direkt für Parameter-Extraktion
            else:
                _LOGGER.info(f"Loading device class for parameter extraction: {device_type}")
                device_class = self.get_device_class(device_type)
                if device_class and hasattr(device_class, 'get_defined_parameters'):
                    defined_params = device_class.get_defined_parameters()
                    _LOGGER.info(f"Used direct device class: {len(defined_params)} parameters for {device_type}")
                    
        except Exception as e:
            _LOGGER.error(f"Error getting defined parameters for {device_type}: {e}")
            _LOGGER.error(f"Detailed error: {traceback.format_exc()}")
            
        # Wenn nichts gefunden wurde, gebe leeres Set zurück
        if not defined_params:
            _LOGGER.warning(f"No defined parameters found for {device_type} - all parameters will be logged only")
        
        # Cache die Ergebnisse
        self.defined_parameters_cache[device_type] = defined_params
        _LOGGER.debug(f"Cached {len(defined_params)} parameters for {device_type}")
            
        return defined_params

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
            _LOGGER.error(f"Failed to load {device_type} device class: {e}")
            _LOGGER.error(f"Detailed error: {traceback.format_exc()}")
            _LOGGER.warning(f"Using DiagnosticDevice as fallback for {device_type}")
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
        """Setup Message Forwarding vom EcoFlow MQTT zum lokalen Broker mit optimierter Keep-Alive Konfiguration"""
        if hasattr(self.api_client, 'mqtt_client') and self.api_client.mqtt_client:
            # Zugriff auf den inneren paho-mqtt Client
            ecoflow_paho_client = self.get_ecoflow_mqtt_client()
            
            if ecoflow_paho_client:
                # Optimiere MQTT Keep-Alive Einstellungen
                try:
                    # Setze robuste Keep-Alive Parameter
                    if hasattr(ecoflow_paho_client, '_keepalive'):
                        original_keepalive = ecoflow_paho_client._keepalive
                        optimized_keepalive = 60  # Standard MQTT Keep-Alive (60 Sekunden)
                        ecoflow_paho_client._keepalive = optimized_keepalive
                        _LOGGER.info(f"MQTT Keep-Alive optimized: {original_keepalive}s → {optimized_keepalive}s")
                    
                    # Setze Socket-Optionen für bessere Stabilität
                    if hasattr(ecoflow_paho_client, '_sock_keepalive'):
                        ecoflow_paho_client._sock_keepalive = True
                        
                    # Setze Standard TCP Socket Keep-Alive Optionen (natürlich)
                    try:
                        import socket
                        if hasattr(ecoflow_paho_client, '_sock') and ecoflow_paho_client._sock:
                            sock = ecoflow_paho_client._sock
                            # Aktiviere TCP Keep-Alive
                            sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
                            # Setze Standard Keep-Alive Parameter (weniger aggressiv)
                            if hasattr(socket, 'TCP_KEEPIDLE'):
                                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 300)  # Start nach 5min (Standard)
                            if hasattr(socket, 'TCP_KEEPINTVL'):
                                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 75)  # Alle 75s (Standard)
                            if hasattr(socket, 'TCP_KEEPCNT'):
                                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 9)   # 9 Versuche (Standard)
                            _LOGGER.info("Standard TCP Keep-Alive configured for MQTT socket")
                    except Exception as tcp_error:
                        _LOGGER.debug(f"TCP Keep-Alive configuration failed: {tcp_error}")
                        
                    # Optimiere Reconnect-Verhalten
                    if hasattr(ecoflow_paho_client, 'reconnect_delay_set'):
                        ecoflow_paho_client.reconnect_delay_set(min_delay=1, max_delay=30)
                        
                    # Wichtig: Initialisiere Message-Timestamps korrekt
                    current_time = time.time()
                    if hasattr(ecoflow_paho_client, '_last_msg_in'):
                        ecoflow_paho_client._last_msg_in = current_time
                    if hasattr(ecoflow_paho_client, '_last_msg_out'):
                        ecoflow_paho_client._last_msg_out = current_time
                    if hasattr(ecoflow_paho_client, '_ping_t'):
                        ecoflow_paho_client._ping_t = 0
                        
                except Exception as keepalive_error:
                    _LOGGER.debug(f"Keep-Alive optimization failed: {keepalive_error}")
                
                # Original-Callbacks sichern
                original_on_message = ecoflow_paho_client.on_message
                original_on_connect = ecoflow_paho_client.on_connect
                original_on_disconnect = ecoflow_paho_client.on_disconnect
                
                # Erweiterte Verbindungsüberwachung
                def connection_wrapper(client, userdata, flags, rc):
                    if rc == 0:
                        _LOGGER.info("EcoFlow MQTT broker connection successfully established")
                        # Reset reconnection counter bei erfolgreicher Verbindung
                        if hasattr(self, 'reconnection_count'):
                            self.reconnection_count = 0
                        if hasattr(self, 'reconnection_in_progress'):
                            self.reconnection_in_progress = False
                            
                        # Initialisiere Message-Timestamps bei neuer Verbindung
                        current_time = time.time()
                        if hasattr(client, '_last_msg_in'):
                            client._last_msg_in = current_time
                        if hasattr(client, '_last_msg_out'):
                            client._last_msg_out = current_time
                    else:
                        _LOGGER.warning(f"EcoFlow MQTT connection failed: RC={rc}")
                    
                    # Original-Callback ausführen
                    if original_on_connect:
                        original_on_connect(client, userdata, flags, rc)
                
                # Disconnect-Überwachung hinzufügen
                def disconnect_wrapper(client, userdata, rc):
                    if rc != 0:
                        _LOGGER.warning(f"🔌 EcoFlow MQTT unexpected disconnect: RC={rc}")
                        # Sanfte Wiederherstellung bei unerwarteter Trennung - threading-sicher
                        if not getattr(self, 'reconnection_in_progress', False):
                            self.schedule_connection_recovery()
                    else:
                        _LOGGER.info("EcoFlow MQTT cleanly disconnected")
                    
                    # Original-Callback ausführen
                    if original_on_disconnect:
                        original_on_disconnect(client, userdata, rc)
                
                # Message-Wrapper mit verbesserter Fehlerbehandlung
                def message_wrapper(client, userdata, message):
                    try:
                        # Aktualisiere Message-Timestamps für Health-Check
                        current_time = time.time()
                        if hasattr(client, '_last_msg_in'):
                            client._last_msg_in = current_time
                        
                        # Original-Callback ausführen
                        if original_on_message:
                            original_on_message(client, userdata, message)
                        
                        # Unsere eigene Verarbeitung
                        self.on_ecoflow_message(client, userdata, message)
                        
                    except Exception as msg_error:
                        _LOGGER.error(f"Message processing error: {msg_error}")
                        # Weiter verarbeiten trotz Fehler
                
                # Wrapper setzen
                ecoflow_paho_client.on_message = message_wrapper
                ecoflow_paho_client.on_connect = connection_wrapper
                ecoflow_paho_client.on_disconnect = disconnect_wrapper
                _LOGGER.info("EcoFlow MQTT message handlers successfully configured")
                
                # Debug: MQTT-Client Status überprüfen (initial)
                _LOGGER.info(f"EcoFlow MQTT Client initial status: Connected={ecoflow_paho_client.is_connected()}")
                if hasattr(ecoflow_paho_client, '_host'):
                    _LOGGER.info(f"EcoFlow MQTT Client host: {ecoflow_paho_client._host}")
                if hasattr(ecoflow_paho_client, '_keepalive'):
                    _LOGGER.info(f"EcoFlow MQTT Keep-Alive interval: {ecoflow_paho_client._keepalive}s")
                
                # Timeout-basierte Reconnection setup (wie ioBroker)
                self.setup_message_timeout_monitoring()
                
            else:
                _LOGGER.warning("Could not access EcoFlow paho-mqtt client")
        else:
            _LOGGER.warning("EcoFlow MQTT client not available for setup")
            _LOGGER.warning("EcoFlow MQTT client not available")

    def setup_message_timeout_monitoring(self):
        """
        Robustes timeout-basiertes Monitoring mit intelligenter Reconnection
        """
        self.last_message_time = time.time()
        self.message_timeout_timer = None
        self.message_timeout_interval = 900  # 15 Minuten (erhöht von 10 Min für Stabilität)
        self.reconnection_in_progress = False
        
        # Starte initial timeout
        self.reset_message_timeout()
        
    def schedule_connection_recovery(self):
        """Threading-sichere Planung der Connection Recovery"""
        try:
            # Setze Flag, um mehrfache Versuche zu vermeiden
            if getattr(self, 'reconnection_in_progress', False):
                _LOGGER.debug("Reconnection already in progress - skipping")
                return
                
            # Threading-sichere Methode: Nutze Timer für delayed execution in main thread
            import threading
            
            def delayed_recovery():
                try:
                    # Prüfe ob eine Event Loop läuft
                    try:
                        loop = asyncio.get_running_loop()
                        if loop and not loop.is_closed():
                            # Nutze thread-safe call_soon_threadsafe
                            loop.call_soon_threadsafe(
                                lambda: asyncio.create_task(self.gentle_connection_recovery())
                            )
                            _LOGGER.info("Connection recovery scheduled via event loop")
                        else:
                            _LOGGER.warning("No active event loop for recovery scheduling")
                    except RuntimeError:
                        # Keine Event Loop verfügbar - nutze synchrone Fallback-Methode
                        _LOGGER.info("No event loop available - using sync recovery fallback")
                        self.sync_connection_recovery()
                        
                except Exception as recovery_error:
                    _LOGGER.error(f"Failed to schedule connection recovery: {recovery_error}")
                    
            # Starte delayed recovery in separatem Thread nach kurzer Verzögerung
            recovery_timer = threading.Timer(2.0, delayed_recovery)
            recovery_timer.daemon = True  # Daemon Thread, damit er das Programm nicht blockiert
            recovery_timer.start()
            
        except Exception as e:
            _LOGGER.error(f"Error in schedule_connection_recovery: {e}")
    
    def sync_connection_recovery(self):
        """Synchrone Fallback-Methode für Connection Recovery ohne Event Loop"""
        try:
            _LOGGER.info("🔧 Starting sync connection recovery...")
            self.reconnection_in_progress = True
            
            mqtt_client = self.get_ecoflow_mqtt_client()
            if not mqtt_client:
                _LOGGER.warning("No MQTT client available for sync recovery")
                return
                
            # Einfache Reconnection-Strategie
            try:
                if hasattr(mqtt_client, 'reconnect'):
                    _LOGGER.info("Attempting MQTT reconnect...")
                    mqtt_client.reconnect()
                    import time
                    time.sleep(3)  # Kurz warten
                    
                    if mqtt_client.is_connected():
                        _LOGGER.info("Sync MQTT reconnect successful")
                    else:
                        _LOGGER.warning("Sync MQTT reconnect completed but not connected")
                        
            except Exception as reconnect_error:
                _LOGGER.error(f"Sync MQTT reconnect failed: {reconnect_error}")
                
        except Exception as e:
            _LOGGER.error(f"Sync connection recovery failed: {e}")
        finally:
            self.reconnection_in_progress = False
        
    def reset_message_timeout(self):
        """Reset message timeout timer nach jeder empfangenen Nachricht"""
        try:
            # Alten Timer stoppen
            if hasattr(self, 'message_timeout_timer') and self.message_timeout_timer:
                self.message_timeout_timer.cancel()
                
            # Neuen Timer starten
            import threading
            self.message_timeout_timer = threading.Timer(
                self.message_timeout_interval, 
                self.handle_message_timeout
            )
            self.message_timeout_timer.start()
            
            _LOGGER.debug(f"Message timeout reset - will trigger in {self.message_timeout_interval}s")
            
        except Exception as e:
            _LOGGER.debug(f"Error resetting message timeout: {e}")
            
    def handle_message_timeout(self):
        """
        Intelligente Timeout-Behandlung mit gestufter Wiederherstellung
        """
        try:
            # Verhindere parallele Reconnection-Versuche
            if getattr(self, 'reconnection_in_progress', False):
                _LOGGER.debug("Reconnection already in progress - skipping timeout handling")
                self.reset_message_timeout()
                return
                
            _LOGGER.warning(f"No messages received in {self.message_timeout_interval}s - analyzing connection")
            
            # Reconnection counter erhöhen
            if not hasattr(self, 'reconnection_count'):
                self.reconnection_count = 0
            self.reconnection_count += 1
            
            # Verbindungsstatus analysieren
            connection_analysis = self.analyze_connection_status()
            
            # Gestufte Wiederherstellung basierend auf Analyse
            if connection_analysis['needs_recovery']:
                # Threading-sichere Planung der Recovery
                self.schedule_intelligent_recovery(connection_analysis)
            else:
                _LOGGER.info("Connection appears healthy despite timeout - resetting timer")
            
            # Statistik publizieren
            if self.mqtt_client:
                timeout_status = {
                    'timeout_triggered': True,
                    'reconnection_count': self.reconnection_count,
                    'last_message_time': self.last_message_time,
                    'timeout_interval': self.message_timeout_interval,
                    'connection_analysis': connection_analysis,
                    'timestamp': time.time()
                }
                
                self.mqtt_client.publish(
                    f"{self.mqtt_base_topic}/timeout_status", 
                    json.dumps(timeout_status), 
                    retain=True
                )
            
            # Timer für nächsten Check wieder starten
            self.reset_message_timeout()
            
        except Exception as e:
            _LOGGER.error(f"Error handling message timeout: {e}")
            
    def analyze_connection_status(self):
        """Analysiert den aktuellen Verbindungsstatus für intelligente Wiederherstellung"""
        analysis = {
            'mqtt_connected': False,
            'mqtt_healthy': False,
            'api_client_available': False,
            'needs_recovery': False,
            'recovery_level': 'none'
        }
        
        try:
            # API Client Status
            analysis['api_client_available'] = bool(self.api_client)
            
            # MQTT Client Status
            mqtt_client = self.get_ecoflow_mqtt_client()
            if mqtt_client:
                analysis['mqtt_connected'] = mqtt_client.is_connected()
                
                # Erweiterte Gesundheitsprüfung
                if analysis['mqtt_connected']:
                    try:
                        # Prüfe letzte Nachricht
                        if hasattr(mqtt_client, '_last_msg_in'):
                            msg_age = time.time() - mqtt_client._last_msg_in
                            analysis['mqtt_healthy'] = msg_age < 1800  # 30 Minuten
                        else:
                            analysis['mqtt_healthy'] = True  # Fallback
                    except:
                        analysis['mqtt_healthy'] = analysis['mqtt_connected']
            
            # Bestimme Wiederherstellungslevel
            if not analysis['api_client_available']:
                analysis['needs_recovery'] = True
                analysis['recovery_level'] = 'full_restart'
            elif not analysis['mqtt_connected']:
                analysis['needs_recovery'] = True
                analysis['recovery_level'] = 'mqtt_reconnect'
            elif not analysis['mqtt_healthy']:
                analysis['needs_recovery'] = True
                analysis['recovery_level'] = 'gentle_recovery'
            else:
                # Verbindung scheint OK - möglicherweise nur temporärer Datenmangel
                analysis['needs_recovery'] = False
                analysis['recovery_level'] = 'none'
                
        except Exception as e:
            _LOGGER.debug(f"Connection analysis error: {e}")
            analysis['needs_recovery'] = True
            analysis['recovery_level'] = 'gentle_recovery'
            
        return analysis

    def schedule_intelligent_recovery(self, analysis):
        """Threading-sichere Planung der intelligenten Connection Recovery"""
        try:
            recovery_level = analysis.get('recovery_level', 'gentle_recovery')
            _LOGGER.info(f"Scheduling {recovery_level} connection recovery...")
            
            # Verhindere mehrfache Versuche
            if getattr(self, 'reconnection_in_progress', False):
                _LOGGER.debug("Reconnection already in progress - skipping intelligent recovery")
                return
                
            import threading
            
            def delayed_intelligent_recovery():
                try:
                    # Prüfe ob eine Event Loop läuft
                    try:
                        loop = asyncio.get_running_loop()
                        if loop and not loop.is_closed():
                            # Nutze thread-safe call_soon_threadsafe
                            loop.call_soon_threadsafe(
                                lambda: asyncio.create_task(self.intelligent_connection_recovery(analysis))
                            )
                            _LOGGER.info("Intelligent recovery scheduled via event loop")
                        else:
                            _LOGGER.warning("No active event loop for intelligent recovery")
                    except RuntimeError:
                        # Keine Event Loop verfügbar - nutze synchrone Fallback-Methode
                        _LOGGER.info("No event loop available - using sync recovery fallback")
                        self.sync_intelligent_recovery(analysis)
                        
                except Exception as recovery_error:
                    _LOGGER.error(f"Failed to schedule intelligent recovery: {recovery_error}")
                    
            # Starte delayed recovery in separatem Thread nach kurzer Verzögerung
            recovery_timer = threading.Timer(1.0, delayed_intelligent_recovery)
            recovery_timer.daemon = True
            recovery_timer.start()
            
        except Exception as e:
            _LOGGER.error(f"Error in schedule_intelligent_recovery: {e}")
    
    def sync_intelligent_recovery(self, analysis):
        """Synchrone Fallback-Methode für intelligente Recovery ohne Event Loop"""
        try:
            recovery_level = analysis.get('recovery_level', 'gentle_recovery')
            _LOGGER.info(f"🔧 Starting sync {recovery_level} recovery...")
            self.reconnection_in_progress = True
            
            if recovery_level == 'gentle_recovery':
                self.sync_connection_recovery()
            elif recovery_level in ['mqtt_reconnect', 'full_restart']:
                # Für komplexere Recovery-Level auch sync fallback
                self.sync_connection_recovery()
                
            _LOGGER.info(f"Sync {recovery_level} recovery completed")
            
        except Exception as e:
            _LOGGER.error(f"Sync intelligent recovery failed: {e}")
        finally:
            self.reconnection_in_progress = False

    async def intelligent_connection_recovery(self, analysis):
        """Gestufte Verbindungswiederherstellung basierend auf Problemanalyse"""
        try:
            self.reconnection_in_progress = True
            recovery_level = analysis.get('recovery_level', 'gentle_recovery')
            
            _LOGGER.info(f"Starting {recovery_level} connection recovery...")
            
            if recovery_level == 'gentle_recovery':
                # Sanfte Wiederherstellung
                await self.gentle_connection_recovery()
                
            elif recovery_level == 'mqtt_reconnect':
                # MQTT-spezifische Wiederherstellung
                await self.mqtt_specific_recovery()
                
            elif recovery_level == 'full_restart':
                # Vollständiger API Client Neustart
                await self.full_api_client_restart()
                
            _LOGGER.info(f"{recovery_level} recovery completed")
            
        except Exception as e:
            _LOGGER.error(f"Connection recovery failed: {e}")
        finally:
            self.reconnection_in_progress = False

    async def mqtt_specific_recovery(self):
        """MQTT-spezifische Wiederherstellung ohne API Client Neustart"""
        try:
            mqtt_client = self.get_ecoflow_mqtt_client()
            if not mqtt_client:
                raise Exception("No MQTT client available")
                
            _LOGGER.info("Attempting MQTT-specific recovery...")
            
            # Versuche sanften Reconnect
            try:
                if hasattr(mqtt_client, 'reconnect'):
                    mqtt_client.reconnect()
                    await asyncio.sleep(5)  # Warten auf Verbindung
                    
                    if mqtt_client.is_connected():
                        _LOGGER.info("MQTT reconnect successful")
                        return
                        
            except Exception as reconnect_error:
                _LOGGER.debug(f"MQTT reconnect failed: {reconnect_error}")
            
            # Fallback: API Client MQTT restart
            if hasattr(self.api_client, 'stop') and hasattr(self.api_client, 'start'):
                _LOGGER.info("Attempting API client MQTT restart...")
                self.api_client.stop()
                await asyncio.sleep(3)
                
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(None, self.api_client.start)
                _LOGGER.info("API client MQTT restart completed")
                
        except Exception as e:
            _LOGGER.error(f"MQTT-specific recovery failed: {e}")
            raise

    async def full_api_client_restart(self):
        """Vollständiger API Client Neustart als letzte Option"""
        try:
            _LOGGER.info("Performing full API client restart...")
            
            # Stoppe alten Client
            if self.api_client and hasattr(self.api_client, 'stop'):
                self.api_client.stop()
                self.api_client = None
                
            await asyncio.sleep(5)  # Cooldown-Periode
            
            # Starte neuen Client
            await self.setup_api_client()
            
            # Message Forwarding neu setup
            self.setup_ecoflow_message_forwarding()
            
            _LOGGER.info("Full API client restart completed")
            
        except Exception as e:
            _LOGGER.error(f"Full API client restart failed: {e}")
            raise

    def on_ecoflow_message(self, client, userdata, message):
        """Callback für EcoFlow MQTT-Nachrichten - nutzt Device-Klassen für Dekodierung"""
        try:
            # Nachrichten-Statistik aktualisieren
            self.message_count = getattr(self, 'message_count', 0) + 1
            self.last_message_time = time.time()
            
            # Message timeout timer zurücksetzen (wie in ioBroker)
            if hasattr(self, 'reset_message_timeout'):
                self.reset_message_timeout()
            
            topic = message.topic
            payload = message.payload
            
            _LOGGER.info(f"EcoFlow MQTT message #{self.message_count} received - Topic: {topic}, Payload size: {len(payload)} bytes")
            
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
                _LOGGER.info(f"Device class decoded {device_type} data: {param_count} parameters")
                
                # Detaillierte Parameter-Info für wichtige Werte
                important_params = self.extract_important_parameters(decoded_data["params"])
                if important_params:
                    _LOGGER.info(f"Key parameters: {', '.join(important_params)}")
                
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
                _LOGGER.warning(f"Device class decoding failed for {device_type}, using hex fallback")
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
            
            # Weiterleitung an lokalen MQTT Broker - nur bei DEBUG Level
            if _LOGGER.isEnabledFor(logging.DEBUG):
                local_topic = f"{self.mqtt_base_topic}/{device_sn}/data"
                self.mqtt_client.publish(local_topic, payload_str, retain=True)
            
            # Geräte-spezifisches Topic wurde entfernt - keine Publikation mehr
            
            # Parameter-spezifische Topics nur für definierte Parameter
            if "params" in mqtt_data and mqtt_data["params"]:
                self.publish_filtered_parameters(device_instance, device_sn, device_type, mqtt_data["params"], mqtt_data.get("timestamp", time.time()))
            
            # Original-Topic Structure wurde entfernt - keine Raw-Publikation mehr
            
            # Log-Ausgabe nur bei DEBUG Level
            if _LOGGER.isEnabledFor(logging.DEBUG):
                local_topic = f"{self.mqtt_base_topic}/{device_sn}/data"
                _LOGGER.debug(f"EcoFlow {device_type} data forwarded: {topic} -> {local_topic}")
            else:
                _LOGGER.info(f"EcoFlow {device_type} message processed (data topics published only in DEBUG mode)")
                
        except Exception as e:
            _LOGGER.error(f"Error forwarding EcoFlow message: {e}")
            import traceback
            _LOGGER.error(traceback.format_exc())

    def decode_with_device_class(self, device_instance, device_sn: str, device_type: str, payload: bytes) -> dict:
        """Nutzt die echte Device-Klasse für die Protobuf-Dekodierung - generisch für alle Gerätetypen"""
        try:
            # Basis-Struktur
            result = {
                "device_sn": device_sn,
                "device_type": device_type,
                "timestamp": time.time(),
                "params": {}
            }
            
            # Device-Klasse für Dekodierung nutzen
            _LOGGER.debug(f"Device instance type: {type(device_instance)}")
            _LOGGER.debug(f"Device instance has _prepare_data: {hasattr(device_instance, '_prepare_data')}")
            
            if hasattr(device_instance, '_prepare_data'):
                # Device hat eigene _prepare_data Methode
                _LOGGER.debug(f"Using _prepare_data method for {device_type}")
                decoded_raw = device_instance._prepare_data(payload)
                
                if decoded_raw and "params" in decoded_raw:
                    result["params"] = decoded_raw["params"]
                    result["decoding_success"] = True
                    _LOGGER.info(f"Device class _prepare_data successful: {len(result['params'])} parameters")
                else:
                    _LOGGER.debug(f"Device _prepare_data returned no params: {decoded_raw}")
                    result["decoding_success"] = False
                    
            elif hasattr(device_instance, 'data') and hasattr(device_instance.data, 'update_data'):
                # Standard BaseDevice mit EcoflowDataHolder
                _LOGGER.debug(f"Using DataHolder for {device_type}")
                
                # Versuche direkte Protobuf-Dekodierung für bessere Ergebnisse
                protobuf_decoded = self.decode_device_protobuf_direct(device_type, payload)
                if protobuf_decoded and protobuf_decoded.get("params"):
                    # Nutze die direkten Protobuf-Ergebnisse
                    device_instance.data.update_data(protobuf_decoded)
                    result["params"] = protobuf_decoded["params"]
                    result["decoding_success"] = True
                    _LOGGER.info(f"Device DataHolder with protobuf successful: {len(result['params'])} parameters")
                else:
                    # Fallback: Hex-Darstellung
                    hex_data = {"params": {"raw_hex": payload.hex(), "raw_length": len(payload)}}
                    device_instance.data.update_data(hex_data)
                    
                    # Daten aus dem DataHolder extrahieren
                    if hasattr(device_instance.data, 'params') and device_instance.data.params:
                        result["params"] = dict(device_instance.data.params)
                        result["decoding_success"] = True
                        _LOGGER.info(f"Device DataHolder fallback successful: {len(result['params'])} parameters")
                    else:
                        _LOGGER.debug(f"Device DataHolder returned no data")
                        result["decoding_success"] = False
            else:
                _LOGGER.warning(f"Device instance {device_type} has no known decoding method")
                
                # Universeller Fallback: Direktes Protobuf-Dekodieren für alle Gerätetypen
                _LOGGER.info(f"Attempting direct protobuf decoding for {device_type}")
                fallback_decoded = self.decode_device_protobuf_direct(device_type, payload)
                if fallback_decoded and fallback_decoded.get("params"):
                    result["params"] = fallback_decoded["params"]
                    result["decoding_success"] = True
                    _LOGGER.info(f"Direct protobuf successful: {len(result['params'])} parameters")
                    return result
                
                result["decoding_success"] = False
            
            return result
            
        except Exception as e:
            _LOGGER.error(f"Device class decoding failed for {device_type}: {e}")
            _LOGGER.error(f"Full traceback: {traceback.format_exc()}")
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

    def publish_filtered_parameters(self, device_instance, device_sn: str, device_type: str, params: dict, timestamp: float):
        """Publiziert nur definierte Parameter über MQTT, loggt alle anderen für mögliche Integration"""
        try:
            # Hole definierte Parameter für dieses Device
            defined_params = self.get_defined_parameters_for_device(device_instance, device_type)
            
            # Separiere Parameter in definierte und undefinierte
            defined_found = {}
            undefined_found = {}
            
            # Spezielle SOC-Parameter immer als definiert behandeln
            soc_patterns = [
                'soc', 'f32showsoc', 'bmsbattsoc', 'cmsbattsoc', 'battery_soc',
                'actsoc', 'targetsoc', 'maxchgsoc', 'mindchgsoc', 'diffsoc',
                'backupreversesoc', 'lcdshowsoc', 'f32lcdshowsoc'
            ]
            
            for param_name, param_value in params.items():
                param_lower = param_name.lower().replace('_', '').replace('.', '')
                
                # Check if it's a SOC parameter or already defined
                is_soc_param = any(soc_pattern in param_lower for soc_pattern in soc_patterns)
                is_defined = param_name in defined_params
                
                if is_defined or is_soc_param:
                    defined_found[param_name] = param_value
                    if is_soc_param and not is_defined:
                        _LOGGER.info(f"SOC parameter '{param_name}' auto-promoted to defined: {param_value}")
                else:
                    undefined_found[param_name] = param_value
            
            # Publiziere nur definierte Parameter über MQTT
            for param_name, param_value in defined_found.items():
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
            
            # Logge undefinierte Parameter für mögliche Integration
            if undefined_found:
                undefined_summary = []
                for param_name, param_value in undefined_found.items():
                    # Erstelle kompakte Darstellung
                    if isinstance(param_value, (int, float)):
                        undefined_summary.append(f"{param_name}={param_value}")
                    elif isinstance(param_value, bool):
                        undefined_summary.append(f"{param_name}={param_value}")
                    elif isinstance(param_value, str) and len(param_value) < 50:
                        undefined_summary.append(f"{param_name}='{param_value}'")
                    else:
                        undefined_summary.append(f"{param_name}=<{type(param_value).__name__}>")
                
                _LOGGER.info(f"UNDEFINED PARAMETERS for {device_type} ({device_sn}): {len(undefined_found)} parameters found")
                _LOGGER.info(f"UNDEFINED PARAMETERS: {', '.join(undefined_summary[:10])}" + 
                           (f" ... and {len(undefined_summary)-10} more" if len(undefined_summary) > 10 else ""))
                
            
            _LOGGER.debug(f"Published {len(defined_found)} defined parameters for {device_sn}, " +
                         f"logged {len(undefined_found)} undefined parameters")
                        
        except Exception as e:
            _LOGGER.error(f"Error in filtered parameter publishing: {e}")
            _LOGGER.error(traceback.format_exc())

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

    def decode_device_protobuf_direct(self, device_type: str, payload: bytes) -> dict:
        """Universelle direkte Protobuf-Dekodierung als Fallback für alle Gerätetypen"""
        try:
            _LOGGER.debug(f"Direct protobuf decoding: {device_type} - {len(payload)} bytes")
            
            # Gerätespezifische Dekodierung basierend auf Gerätetyp
            if device_type in ["STREAM_ULTRA", "STREAM_AC", "STREAM_PRO"]:
                return self._decode_stream_protobuf(payload)
            elif device_type in ["DELTA_2", "DELTA_2_MAX", "DELTA_PRO", "DELTA_MAX", "DELTA_MINI"]:
                return self._decode_delta_protobuf(payload)
            elif device_type in ["RIVER_2", "RIVER_2_MAX", "RIVER_2_PRO", "RIVER_MAX", "RIVER_MINI", "RIVER_PRO"]:
                return self._decode_river_protobuf(payload)
            elif device_type == "POWERSTREAM":
                return self._decode_powerstream_protobuf(payload)
            elif device_type == "GLACIER":
                return self._decode_glacier_protobuf(payload)
            elif device_type == "WAVE_2":
                return self._decode_wave_protobuf(payload)
            elif device_type == "SMART_METER":
                return self._decode_smart_meter_protobuf(payload)
            else:
                # Universeller Fallback für unbekannte Gerätetypen
                return self._decode_generic_protobuf(payload)
                
        except Exception as e:
            _LOGGER.debug(f"Direct protobuf decoding failed for {device_type}: {e}")
            return {"params": {}}
    def _decode_stream_protobuf(self, payload: bytes) -> dict:
        """Dekodiert Stream AC/Ultra/Pro Protobuf-Daten"""
        try:
            from custom_components.ecoflow_cloud.devices.internal.proto import stream_ac_pb2
            
            # Versuche als SendHeaderStreamMsg
            try:
                packet = stream_ac_pb2.SendHeaderStreamMsg()
                packet.ParseFromString(payload)
                
                decoded = {"params": {}}
                
                if hasattr(packet, 'msg') and packet.msg:
                    _LOGGER.debug("SendHeaderStreamMsg.msg found")
                    
                    # Sichere Header-Felder extrahieren
                    for field_name in ['cmd_id', 'src', 'dest', 'seq']:
                        if hasattr(packet.msg, field_name):
                            try:
                                if packet.msg.HasField(field_name):
                                    value = getattr(packet.msg, field_name)
                                    decoded["params"][field_name] = value
                            except Exception:
                                continue
                    
                    # pdata verarbeiten
                    if hasattr(packet.msg, "pdata") and packet.msg.pdata and len(packet.msg.pdata) > 0:
                        pdata = packet.msg.pdata
                        _LOGGER.debug(f"Stream pdata found: {len(pdata)} bytes")
                        
                        # Liste der Stream-Message-Typen
                        stream_types = [
                            ("Champ_cmd21_3", stream_ac_pb2.Champ_cmd21_3),
                            ("Champ_cmd21", stream_ac_pb2.Champ_cmd21), 
                            ("Champ_cmd50", stream_ac_pb2.Champ_cmd50),
                            ("Champ_cmd50_3", stream_ac_pb2.Champ_cmd50_3),
                            ("HeaderStream", stream_ac_pb2.HeaderStream)
                        ]
                        
                        for stream_name, stream_class in stream_types:
                            try:
                                content = stream_class()
                                content.ParseFromString(pdata)
                                
                                content_str = str(content)
                                if len(content_str) > 0 and content_str.strip():
                                    _LOGGER.debug(f"Successfully parsed {stream_name}")
                                    
                                    # Extrahiere alle verfügbaren Felder
                                    for descriptor in content.DESCRIPTOR.fields:
                                        try:
                                            if not content.HasField(descriptor.name):
                                                continue
                                            
                                            value = getattr(content, descriptor.name)
                                            field_name = descriptor.name
                                            
                                            # Parameter verarbeiten
                                            self._process_stream_field(decoded["params"], field_name, value)
                                            
                                        except Exception as field_error:
                                            _LOGGER.debug(f"Failed to process field {descriptor.name}: {field_error}")
                                            continue
                                    
                                    # Wenn wir wichtige Parameter gefunden haben, früh zurückkehren
                                    if self._has_important_parameters(decoded["params"]):
                                        _LOGGER.info(f"Found key parameters in {stream_name}")
                                        break
                            
                            except Exception as e:
                                _LOGGER.debug(f"Failed to parse {stream_name}: {e}")
                                continue
                
                if decoded["params"]:
                    _LOGGER.info(f"Stream protobuf decoding successful: {len(decoded['params'])} parameters")
                    return decoded
                    
            except Exception as stream_error:
                _LOGGER.debug(f"Stream protobuf decoding failed: {stream_error}")
            
            return {"params": {}}
            
        except ImportError as e:
            _LOGGER.debug(f"Cannot import stream_ac_pb2 for direct decoding: {e}")
            return {"params": {}}
        except Exception as e:
            _LOGGER.debug(f"Stream protobuf decoding completely failed: {e}")
            return {"params": {}}

    def _process_stream_field(self, params: dict, field_name: str, value):
        """Verarbeitet Stream-Felder und fügt sie zu den Parametern hinzu"""
        try:
            # Spezielle Stream-Parameter verarbeiten
            if field_name == "f32ShowSoc":
                params["battery_soc"] = round(value, 2)
                params["f32ShowSoc"] = value
                _LOGGER.info(f"Found Battery SOC: {params['battery_soc']}%")
            elif field_name == "bmsBattSoc":
                params["bms_battery_soc"] = round(value, 2)  
                params["bmsBattSoc"] = value
                _LOGGER.info(f"Found BMS Battery SOC: {params['bms_battery_soc']}%")
            elif field_name == "soc":
                params["soc"] = value
                params["battery_percentage"] = value
                _LOGGER.info(f"Found SOC: {value}%")
            elif field_name == "cycles":
                params["battery_cycles"] = value
                params["cycles"] = value
                _LOGGER.info(f"Found Battery cycles: {value}")
            elif field_name in ["gridConnectionPower", "inputWatts", "outputWatts"]:
                params[field_name] = round(value, 2)
                _LOGGER.info(f"Found {field_name}: {params[field_name]}W")
            else:
                params[field_name] = value
                _LOGGER.debug(f"Found {field_name}: {value}")
        except Exception as e:
            _LOGGER.debug(f"Error processing stream field {field_name}: {e}")

    def _has_important_parameters(self, params: dict) -> bool:
        """Prüft ob wichtige Parameter gefunden wurden"""
        important_keys = ["battery_soc", "soc", "f32ShowSoc", "bmsBattSoc", "gridConnectionPower"]
        return any(key in params for key in important_keys)

    def _decode_delta_protobuf(self, payload: bytes) -> dict:
        """Dekodiert Delta Protobuf-Daten"""
        try:
            # Versuche mit generischen EcoPacket
            from custom_components.ecoflow_cloud.devices.internal.proto import ecopacket_pb2
            
            try:
                packet = ecopacket_pb2.Message()
                packet.ParseFromString(payload)
                
                decoded = {"params": {}}
                self._extract_common_packet_fields(packet, decoded["params"])
                
                if decoded["params"]:
                    _LOGGER.info(f"Delta protobuf decoding successful: {len(decoded['params'])} parameters")
                    return decoded
                    
            except Exception as e:
                _LOGGER.debug(f"Delta protobuf parsing failed: {e}")
            
            return {"params": {}}
            
        except ImportError as e:
            _LOGGER.debug(f"Cannot import protobuf modules for Delta: {e}")
            return {"params": {}}

    def _decode_river_protobuf(self, payload: bytes) -> dict:
        """Dekodiert River Protobuf-Daten"""
        try:
            # Versuche mit generischen EcoPacket
            from custom_components.ecoflow_cloud.devices.internal.proto import ecopacket_pb2
            
            try:
                packet = ecopacket_pb2.Message()
                packet.ParseFromString(payload)
                
                decoded = {"params": {}}
                self._extract_common_packet_fields(packet, decoded["params"])
                
                if decoded["params"]:
                    _LOGGER.info(f"River protobuf decoding successful: {len(decoded['params'])} parameters")
                    return decoded
                    
            except Exception as e:
                _LOGGER.debug(f"River protobuf parsing failed: {e}")
            
            return {"params": {}}
            
        except ImportError as e:
            _LOGGER.debug(f"Cannot import protobuf modules for River: {e}")
            return {"params": {}}

    def _decode_powerstream_protobuf(self, payload: bytes) -> dict:
        """Dekodiert PowerStream Protobuf-Daten"""
        try:
            # Versuche mit PowerStream-spezifischen Protobuf
            from custom_components.ecoflow_cloud.devices.internal.proto import powerstream_pb2
            
            try:
                packet = powerstream_pb2.PowerStreamMessage()
                packet.ParseFromString(payload)
                
                decoded = {"params": {}}
                self._extract_common_packet_fields(packet, decoded["params"])
                
                if decoded["params"]:
                    _LOGGER.info(f"PowerStream protobuf decoding successful: {len(decoded['params'])} parameters")
                    return decoded
                    
            except Exception as e:
                _LOGGER.debug(f"PowerStream protobuf parsing failed: {e}")
            
            # Fallback zu generischem EcoPacket
            return self._decode_generic_protobuf(payload)
            
        except ImportError as e:
            _LOGGER.debug(f"Cannot import powerstream_pb2: {e}")
            return self._decode_generic_protobuf(payload)

    def _decode_glacier_protobuf(self, payload: bytes) -> dict:
        """Dekodiert Glacier Protobuf-Daten"""
        try:
            # Fallback zu generischem EcoPacket
            return self._decode_generic_protobuf(payload)
        except Exception as e:
            _LOGGER.debug(f"Glacier protobuf decoding failed: {e}")
            return {"params": {}}

    def _decode_wave_protobuf(self, payload: bytes) -> dict:
        """Dekodiert Wave Protobuf-Daten"""
        try:
            # Fallback zu generischem EcoPacket
            return self._decode_generic_protobuf(payload)
        except Exception as e:
            _LOGGER.debug(f"Wave protobuf decoding failed: {e}")
            return {"params": {}}

    def _decode_smart_meter_protobuf(self, payload: bytes) -> dict:
        """Dekodiert Smart Meter Protobuf-Daten"""
        try:
            # Fallback zu generischem EcoPacket
            return self._decode_generic_protobuf(payload)
        except Exception as e:
            _LOGGER.debug(f"Smart Meter protobuf decoding failed: {e}")
            return {"params": {}}

    def _decode_generic_protobuf(self, payload: bytes) -> dict:
        """Universeller Fallback für alle unbekannten Gerätetypen"""
        try:
            # Versuche mit generischen EcoPacket
            from custom_components.ecoflow_cloud.devices.internal.proto import ecopacket_pb2
            
            try:
                packet = ecopacket_pb2.Message()
                packet.ParseFromString(payload)
                
                decoded = {"params": {}}
                self._extract_common_packet_fields(packet, decoded["params"])
                
                if decoded["params"]:
                    _LOGGER.info(f"Generic protobuf decoding successful: {len(decoded['params'])} parameters")
                    return decoded
                    
            except Exception as e:
                _LOGGER.debug(f"Generic protobuf parsing failed: {e}")
            
            # Fallback: Hex-Analyse
            return self._analyze_hex_data(payload)
            
        except ImportError as e:
            _LOGGER.debug(f"Cannot import ecopacket_pb2: {e}")
            return self._analyze_hex_data(payload)

    def _extract_common_packet_fields(self, packet, params: dict):
        """Extrahiert gemeinsame Felder aus EcoPacket-Strukturen"""
        try:
            # Standard EcoPacket Felder
            common_fields = ['cmd_func', 'cmd_id', 'device_sn', 'src', 'dest', 'seq']
            
            for field_name in common_fields:
                if hasattr(packet, field_name):
                    try:
                        if packet.HasField(field_name):
                            value = getattr(packet, field_name)
                            params[field_name] = value
                            _LOGGER.debug(f"{field_name}: {value}")
                    except Exception:
                        continue
            
            # Data-Feld verarbeiten wenn vorhanden
            if hasattr(packet, 'data') and packet.HasField('data'):
                data_field = packet.data
                _LOGGER.debug(f"Packet data field found: {len(data_field)} bytes")
                
                # Versuche data-Feld als weitere Protobuf-Struktur zu dekodieren
                # Dies ist geräte-spezifisch, daher nur grundlegende Analyse
                params["data_length"] = len(data_field)
                params["data_hex"] = data_field.hex()[:100] + "..." if len(data_field.hex()) > 100 else data_field.hex()
                
        except Exception as e:
            _LOGGER.debug(f"Error extracting common packet fields: {e}")

    def _analyze_hex_data(self, payload: bytes) -> dict:
        """Analysiert Hex-Daten um mögliche Informationen zu extrahieren"""
        try:
            analysis = {
                "params": {
                    "raw_hex": payload.hex()[:200] + "..." if len(payload.hex()) > 200 else payload.hex(),
                    "raw_length": len(payload),
                    "first_bytes": payload[:8].hex() if len(payload) >= 8 else payload.hex(),
                    "last_bytes": payload[-8:].hex() if len(payload) >= 8 else "",
                }
            }
            
            # Suche nach bekannten Patterns
            hex_str = payload.hex()
            
            # Protobuf-typische Patterns
            if "0a" in hex_str[:20]:
                analysis["params"]["protobuf_pattern"] = True
            
            # Versuche Float-Werte zu finden (SOC könnte als Float kodiert sein)
            import struct
            float_candidates = []
            for i in range(0, len(payload) - 3, 4):
                try:
                    float_val = struct.unpack('<f', payload[i:i+4])[0]
                    if 0 <= float_val <= 100:
                        float_candidates.append((i, float_val))
                except:
                    continue
            
            if float_candidates:
                analysis["params"]["potential_soc_values"] = [f"{val:.2f}" for _, val in float_candidates[:3]]
            
            _LOGGER.debug(f"Hex analysis: {len(payload)} bytes -> {len(analysis['params'])} analysis fields")
            return analysis
            
        except Exception as e:
            _LOGGER.debug(f"Hex analysis failed: {e}")
            return {"params": {"raw_hex": payload.hex() if payload else "", "raw_length": len(payload) if payload else 0}}
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
                
                _LOGGER.info(f"EcoPacket Message parsing successful")
                
                decoded["protobuf_success"] = True
                decoded["message_type"] = "EcoPacketMessage"
                
                # Extrahiere Felder aus Message
                if hasattr(packet, 'cmd_func') and packet.HasField('cmd_func'):
                    decoded["params"]["cmd_func"] = packet.cmd_func
                    _LOGGER.info(f"cmd_func: {packet.cmd_func}")
                
                if hasattr(packet, 'cmd_id') and packet.HasField('cmd_id'):
                    decoded["params"]["cmd_id"] = packet.cmd_id
                    _LOGGER.info(f"cmd_id: {packet.cmd_id}")
                
                if hasattr(packet, 'device_sn') and packet.HasField('device_sn'):
                    decoded["params"]["device_sn"] = packet.device_sn
                    _LOGGER.info(f"device_sn: {packet.device_sn}")
                
                # Wichtig: data Feld verarbeiten
                if hasattr(packet, 'data') and packet.HasField('data'):
                    data_field = packet.data
                    _LOGGER.info(f"EcoPacket data field found: {len(data_field)} bytes")
                    
                    # Versuche data als Stream-spezifischen Content zu dekodieren
                    stream_data = self.decode_stream_data_field(data_field)
                    if stream_data:
                        decoded["params"].update(stream_data)
                        _LOGGER.info(f"Stream data decoded: {len(stream_data)} parameters")
                
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
                
                _LOGGER.info(f"SendHeaderStreamMsg parsing successful (fallback)")
                
                decoded["protobuf_success"] = True
                decoded["message_type"] = "SendHeaderStreamMsg"
                
                # Sichere Attribut-Zugriffe ohne problematische Felder
                if hasattr(packet, 'msg') and packet.msg:
                    _LOGGER.info(f"SendHeaderStreamMsg.msg found")
                    
                    # Nur sichere Felder verwenden
                    for field_name in ['cmd_id', 'src', 'dest', 'check_num', 'seq', 'version']:
                        if hasattr(packet.msg, field_name):
                            try:
                                if packet.msg.HasField(field_name):
                                    value = getattr(packet.msg, field_name)
                                    decoded["params"][field_name] = value
                                    _LOGGER.debug(f"{field_name}: {value}")
                            except Exception:
                                continue
                    
                    # Verarbeite pdata wenn vorhanden
                    if hasattr(packet.msg, "pdata") and packet.msg.pdata and len(packet.msg.pdata) > 0:
                        pdata = packet.msg.pdata
                        _LOGGER.info(f"Stream pdata found: {len(pdata)} bytes")
                        
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
                        _LOGGER.info(f"Successfully parsed {stream_name}")
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
                                    _LOGGER.info(f"Battery SOC: {result['battery_soc']}%")
                                elif field_name == "bmsBattSoc":
                                    result["bms_battery_soc"] = round(value, 2)  
                                    result["bmsBattSoc"] = value
                                    _LOGGER.info(f"BMS Battery SOC: {result['bms_battery_soc']}%")
                                elif field_name == "soc":
                                    result["soc"] = value
                                    result["battery_percentage"] = value
                                    _LOGGER.info(f"SOC: {value}%")
                                elif field_name in ["bmsChgRemTime", "bmsDsgRemTime"]:
                                    result[field_name] = value
                                    if field_name == "bmsChgRemTime":
                                        result["charge_remaining_minutes"] = value
                                        _LOGGER.info(f"Charge remaining: {value} min")
                                    elif field_name == "bmsDsgRemTime":
                                        result["discharge_remaining_minutes"] = value
                                        _LOGGER.info(f"Discharge remaining: {value} min")
                                elif field_name == "cycles":
                                    result["battery_cycles"] = value
                                    result["cycles"] = value
                                    _LOGGER.info(f"Battery cycles: {value}")
                                elif field_name in ["designCap", "fullCap", "remainCap"]:
                                    result[field_name] = value
                                    _LOGGER.info(f"{field_name}: {value}")
                                elif field_name in ["gridConnectionPower", "inputWatts", "outputWatts"]:
                                    result[field_name] = round(value, 2)
                                    _LOGGER.info(f"{field_name}: {result[field_name]}W")
                                elif field_name in ["powGetPvSum", "powGetBpCms", "powGetSysGrid"]:
                                    result[field_name] = round(value, 2)
                                    _LOGGER.info(f"{field_name}: {result[field_name]}W")
                                elif field_name in ["maxCellTemp", "minCellTemp", "temp"]:
                                    result[field_name] = value
                                    _LOGGER.debug(f"{field_name}: {value}°C")
                                elif field_name in ["maxCellVol", "minCellVol", "vol"]:
                                    result[field_name] = value
                                    _LOGGER.debug(f"{field_name}: {value}V")
                                else:
                                    result[field_name] = value
                                    _LOGGER.debug(f"{field_name}: {value}")
                                    
                            except Exception as field_error:
                                _LOGGER.debug(f"Failed to process field {descriptor.name}: {field_error}")
                                continue
                        
                        _LOGGER.info(f"{stream_name}: extracted {field_count} fields")
                        
                        # Wenn wir wichtige Parameter gefunden haben, können wir früh zurückkehren
                        if any(key in result for key in ["battery_soc", "soc", "battery_percentage"]):
                            _LOGGER.info(f"Found key battery parameters in {stream_name}")
                            break
                
                except Exception as e:
                    _LOGGER.debug(f"Failed to parse {stream_name}: {e}")
                    continue
            
            if success_count > 0:
                _LOGGER.info(f"Stream data parsing successful: {success_count} message types parsed, {len(result)} total parameters")
                
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
                    _LOGGER.info(f"Key parameters: {', '.join(key_params)}")
                
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
            
            # Spezielle Hex-Patterns für EcoFlow Geräte
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

    async def send_keep_alive_messages(self):
        """
        Verstärkte Keep-Alive Implementierung mit mehrschichtigen Aktivitätssignalen
        Kombiniert API-, MQTT- und Anwendungsebene Keep-Alive für maximale Stabilität
        """
        if not self.api_client:
            _LOGGER.warning("API Client not available for keep-alive")
            return
            
        try:
            keep_alive_success = False
            
            # 1. API-Level Keep-Alive: Quota-Anfragen (primärer Mechanismus)
            try:
                if hasattr(self.api_client, 'quota_all'):
                    await self.api_client.quota_all(None)
                    keep_alive_success = True
                    _LOGGER.debug("quota_all Keep-Alive sent successfully")
                    
                # Zusätzliche Device-spezifische Quota-Anfragen für Activity-Signal
                for device_sn in self.device_sns:
                    try:
                        if hasattr(self.api_client, 'get_device_quota'):
                            await self.api_client.get_device_quota(device_sn)
                        elif hasattr(self.api_client, 'get_device_info'):
                            await self.api_client.get_device_info(device_sn)
                    except Exception as device_error:
                        _LOGGER.debug(f"Device quota failed for {device_sn}: {device_error}")
                        continue
                        
            except Exception as quota_error:
                _LOGGER.warning(f"API-level keep-alive failed: {quota_error}")
            
            # 2. MQTT-Level Keep-Alive: Verstärkte Stream Ultra-spezifische Aktivität
            try:
                mqtt_client = self.get_ecoflow_mqtt_client()
                if mqtt_client and mqtt_client.is_connected():
                    # Stream Ultra spezifische Keep-Alive Nachrichten
                    for device_sn in self.device_sns:
                        try:
                            device_type = self.detect_device_type(device_sn)
                            current_time = int(time.time() * 1000)
                            
                            if device_type in ["STREAM_ULTRA", "STREAM_AC", "STREAM_PRO"]:
                                # Stream Ultra optimierte Keep-Alive mit besserer Antwortrate
                                
                                # 1. Quota-Anfrage mit Stream-spezifischen Parametern
                                quota_topic = f"/app/device/quota/{device_sn}"
                                quota_payload = {
                                    "id": current_time % 10000,  # Eindeutige ID
                                    "version": "1.0",
                                    "params": {
                                        "typeMap": 1,
                                        "quotaMap": 1
                                    },
                                    "timestamp": current_time
                                }
                                result1 = mqtt_client.publish(quota_topic, json.dumps(quota_payload), qos=1)
                                
                                # 2. Stream Ultra optimierte Property-Get mit allen wichtigen Parametern
                                get_topic = f"/app/device/property/{device_sn}/get"
                                get_payload = {
                                    "id": (current_time + 1) % 10000,
                                    "version": "1.0",
                                    "params": {
                                        "quotaMap": 1,
                                        "streamData": 1,
                                        "batteryData": 1,
                                        "invData": 1,     # Inverter-Daten
                                        "statusData": 1,  # Status-Daten
                                        "realTimeData": 1 # Echtzeit-Daten
                                    },
                                    "timestamp": current_time
                                }
                                result2 = mqtt_client.publish(get_topic, json.dumps(get_payload), qos=1)
                                
                                # 3. Stream Ultra Thing-Property mit korrektem cmdSet
                                thing_topic = f"/app/{getattr(self, 'username', 'user')}/{device_sn}/thing/property/get"
                                thing_payload = {
                                    "id": (current_time + 2) % 10000,
                                    "version": "1.0",
                                    "params": {
                                        "cmdSet": 3,    # Korrektes Stream Ultra cmdSet
                                        "cmdId": 254,   # All-Status Command
                                        "dataType": 0   # Standard Datentyp
                                    },
                                    "timestamp": current_time
                                }
                                result3 = mqtt_client.publish(thing_topic, json.dumps(thing_payload), qos=1)
                                
                                success_count = sum([r.rc == mqtt.MQTT_ERR_SUCCESS for r in [result1, result2, result3]])
                                _LOGGER.debug(f"Enhanced MQTT keep-alive sent for {device_sn} ({success_count}/3 messages)")
                                
                                # 4. Zusätzliche Stream Ultra-spezifische Wakeup-Nachricht
                                if success_count >= 2:  # Nur wenn andere Nachrichten erfolgreich waren
                                    wakeup_topic = f"/app/{getattr(self, 'username', 'user')}/{device_sn}/thing/property/set"
                                    wakeup_payload = {
                                        "id": (current_time + 3) % 10000,
                                        "version": "1.0",
                                        "params": {
                                            "cmdSet": 21,     # Stream Ultra Status Command Set
                                            "cmdId": 254,     # All Status Command
                                            "dataType": 1
                                        },
                                        "timestamp": current_time
                                    }
                                    result4 = mqtt_client.publish(wakeup_topic, json.dumps(wakeup_payload), qos=1)
                                    if result4.rc == mqtt.MQTT_ERR_SUCCESS:
                                        _LOGGER.debug(f"Stream Ultra wakeup message sent for {device_sn}")
                                        success_count += 1
                                
                            else:
                                # Standard Keep-Alive für andere Geräte
                                quota_topic = f"/app/device/quota/{device_sn}"
                                quota_payload = {
                                    "id": 999,
                                    "version": "1.0",
                                    "params": {},
                                    "timestamp": current_time
                                }
                                result1 = mqtt_client.publish(quota_topic, json.dumps(quota_payload), qos=1)
                                
                                get_topic = f"/app/device/property/{device_sn}/get"
                                get_payload = {
                                    "id": 1000,
                                    "version": "1.0",
                                    "params": {"quotaMap": 1},
                                    "timestamp": current_time
                                }
                                result2 = mqtt_client.publish(get_topic, json.dumps(get_payload), qos=1)
                                
                                success_count = sum([r.rc == mqtt.MQTT_ERR_SUCCESS for r in [result1, result2]])
                                _LOGGER.debug(f"Standard MQTT keep-alive sent for {device_sn} ({success_count}/2 messages)")
                            
                            # 3. Spezielle Geräteaktivierung (falls nötig)
                            stream_topic = f"/app/{self.username}/{device_sn}/thing/property/get"
                            stream_payload = {
                                "id": 1001,
                                "version": "1.0",
                                "params": {"cmdSet": 20, "cmdId": 1},  # Stream-spezifische IDs
                                "timestamp": int(time.time() * 1000)
                            }
                            
                            result3 = mqtt_client.publish(stream_topic, json.dumps(stream_payload), qos=1)
                            
                            if all(r.rc == mqtt.MQTT_ERR_SUCCESS for r in [result1, result2, result3]):
                                keep_alive_success = True
                                _LOGGER.debug(f"Enhanced MQTT keep-alive sent for {device_sn} (3 messages)")
                            else:
                                _LOGGER.debug(f"Some MQTT keep-alive messages failed for {device_sn}")
                                
                        except Exception as heartbeat_error:
                            _LOGGER.debug(f"Enhanced heartbeat failed for {device_sn}: {heartbeat_error}")
                            continue
                    
                    # 4. MQTT-Level Ping für Socket-Keep-Alive
                    try:
                        if hasattr(mqtt_client, 'ping'):
                            mqtt_client.ping()
                            _LOGGER.debug("MQTT ping sent for socket maintenance")
                            keep_alive_success = True
                    except Exception as ping_error:
                        _LOGGER.debug(f"MQTT ping failed: {ping_error}")
                else:
                    _LOGGER.warning("MQTT client not available or not connected")
                        
            except Exception as mqtt_error:
                _LOGGER.warning(f"MQTT-level keep-alive failed: {mqtt_error}")
            
            # Status-Log
            if keep_alive_success:
                _LOGGER.info(f"Enhanced Keep-Alive successful for {len(self.device_sns)} devices")
            else:
                _LOGGER.warning("Keep-Alive failed - triggering connection recovery")
                # Sanfte Verbindungswiederherstellung statt aggressiven Reconnect
                await self.gentle_connection_recovery()
                
        except Exception as e:
            _LOGGER.error(f"Keep-Alive system error: {e}")
            _LOGGER.error(f"Full traceback: {traceback.format_exc()}")

    def get_ecoflow_mqtt_client(self):
        """Holt den EcoFlow MQTT Client mit robuster Fehlerbehandlung"""
        try:
            if not (hasattr(self.api_client, 'mqtt_client') and self.api_client.mqtt_client):
                return None
                
            # Versuche verschiedene Zugriffsmethoden
            for attr_name in ['_EcoflowMQTTClient__client', '__client', 'client']:
                if hasattr(self.api_client.mqtt_client, attr_name):
                    client = getattr(self.api_client.mqtt_client, attr_name)
                    if client and hasattr(client, 'is_connected'):
                        return client
                        
            return None
        except Exception as e:
            _LOGGER.debug(f"Error accessing MQTT client: {e}")
            return None

    async def check_mqtt_connection_health(self, mqtt_client):
        """Erweiterte MQTT-Verbindungsprüfung mit Reconnect-freundlicher Logik"""
        try:
            if not mqtt_client:
                _LOGGER.debug("No MQTT client available")
                return False
                
            # Basis-Verbindungsprüfung
            if not mqtt_client.is_connected():
                _LOGGER.debug("MQTT client reports disconnected")
                return False
            
            # Nach Reconnect ist die Verbindung erstmal als gesund zu betrachten
            _LOGGER.debug("MQTT client reports connected - connection healthy")
            
            # Erweiterte Gesundheitsprüfung nur wenn schon länger verbunden
            try:
                # Prüfe ob Client noch responsive ist
                if hasattr(mqtt_client, '_sock') and mqtt_client._sock:
                    # Socket ist verfügbar - das ist ein gutes Zeichen
                    _LOGGER.debug("MQTT socket available and active")
                    
                    if hasattr(mqtt_client, '_last_msg_in'):
                        # Korrekte Zeitstempel-Berechnung
                        current_time = time.time()
                        last_msg_time = mqtt_client._last_msg_in
                        
                        # Prüfe ob _last_msg_in sinnvoll ist (Unix timestamp)
                        if last_msg_time > 1000000000:  # Nach 2001 (sinnvoller Unix timestamp)
                            last_msg_age = current_time - last_msg_time
                            # Sehr tolerant nach Reconnect: 20 Minuten statt 15
                            if last_msg_age > 1200:  # 20 Minuten ohne Nachrichten
                                _LOGGER.debug(f"No messages received for {last_msg_age:.1f}s - connection may be stale")
                                return False
                            else:
                                _LOGGER.debug(f"Last message received {last_msg_age:.1f}s ago - connection healthy")
                        else:
                            # _last_msg_in ist nicht initialisiert oder fehlerhaft
                            _LOGGER.debug("_last_msg_in not properly initialized - assuming healthy for connected client")
                            # Setze current time als Fallback
                            mqtt_client._last_msg_in = current_time
                    else:
                        _LOGGER.debug("MQTT client has no _last_msg_in attribute - assuming healthy for connected client")
                        # Setze aktuellen Zeitstempel
                        mqtt_client._last_msg_in = time.time()
                else:
                    _LOGGER.debug("MQTT client socket not available but client reports connected - assuming healthy")
                    # Wenn Socket nicht verfügbar ist aber Client meldet "connected", geben wir trotzdem OK
                    
            except Exception as health_error:
                _LOGGER.debug(f"Extended health check failed: {health_error}")
                # Fallback: Wenn erweiterte Prüfung fehlschlägt aber is_connected() True ist,
                # dann ist die Verbindung wahrscheinlich in Ordnung
                _LOGGER.debug("Falling back to basic connection check - client reports connected")
                
            return True  # Wenn is_connected() True ist, ist die Verbindung gesund
            
        except Exception as e:
            _LOGGER.debug(f"Connection health check error: {e}")
            return False

    async def send_enhanced_app_simulation(self):
        """
        Enhanced App Simulation: Simulates EcoFlow app startup sequence
        to trigger data flow after reconnects or initial startup
        Improved version with more authentic message sequence
        """
        if not self.api_client:
            return False
            
        try:
            mqtt_client = self.get_ecoflow_mqtt_client()
            if not mqtt_client:
                _LOGGER.warning("No MQTT client for app simulation")
                return False
                
            _LOGGER.info("Starting enhanced app simulation sequence...")
            
            simulation_success = 0
            total_attempts = 0
            
            for device_sn in self.device_sns:
                try:
                    # Nutze detect_device_type für Typ-spezifische Simulation
                    device_type = self.detect_device_type(device_sn)
                    _LOGGER.info(f"Starting app simulation for {device_type} device: {device_sn}")
                    
                    # === Phase 1: Initial Quota Request (App-Startup) ===
                    quota_topic = f"/app/device/quota/{device_sn}"
                    quota_payload = {
                        "id": self.get_next_message_id(),
                        "version": "1.0", 
                        "params": {},
                        "timestamp": int(time.time() * 1000)
                    }
                    result = mqtt_client.publish(quota_topic, json.dumps(quota_payload), qos=1)
                    if result.rc == mqtt.MQTT_ERR_SUCCESS:
                        simulation_success += 1
                        _LOGGER.info(f"Quota request sent for {device_sn}")
                    total_attempts += 1
                    
                    await asyncio.sleep(1.0)  # Längere Pause für Server-Verarbeitung
                    
                    # === Phase 2: Property Get Request mit QuotaMap ===
                    prop_topic = f"/app/device/property/{device_sn}/get"
                    prop_payload = {
                        "id": self.get_next_message_id(),
                        "version": "1.0",
                        "params": {"quotaMap": 1},
                        "timestamp": int(time.time() * 1000)
                    }
                    result = mqtt_client.publish(prop_topic, json.dumps(prop_payload), qos=1)
                    if result.rc == mqtt.MQTT_ERR_SUCCESS:
                        simulation_success += 1
                        _LOGGER.info(f"Property request sent for {device_sn}")
                    total_attempts += 1
                    
                    await asyncio.sleep(1.0)
                    
                    # === Phase 3: Device-spezifische Thing Property Requests ===
                    if "stream" in device_type.lower() or "ultra" in device_type.lower():
                        # Stream Ultra: Mehrere spezifische Anfragen für bessere Aktivierung
                        stream_requests = [
                            {"cmdSet": 3, "cmdId": 254, "dataType": 0},  # Standard Wakeup
                            {"cmdSet": 3, "cmdId": 1, "dataType": 0},    # Status Request
                            {"cmdSet": 11, "cmdId": 1, "dataType": 0},   # Battery Info
                        ]
                        
                        for i, params in enumerate(stream_requests):
                            thing_topic = f"/app/{self.username}/{device_sn}/thing/property/get"
                            thing_payload = {
                                "id": self.get_next_message_id(),
                                "version": "1.0",
                                "params": params,
                                "timestamp": int(time.time() * 1000)
                            }
                            
                            result = mqtt_client.publish(thing_topic, json.dumps(thing_payload), qos=1)
                            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                                simulation_success += 1
                                _LOGGER.info(f"Stream Ultra request {i+1}/3 sent for {device_sn}")
                            total_attempts += 1
                            
                            await asyncio.sleep(0.8)  # Kurze Pause zwischen Stream-Requests
                            
                        _LOGGER.info(f"Stream Ultra parameters used for {device_sn}")
                    else:
                        # Standard Geräte: Mehrere Standard-Requests
                        standard_requests = [
                            {"cmdSet": 20, "cmdId": 1},     # Standard Status
                            {"cmdSet": 6, "cmdId": 1},      # Battery Status
                            {"cmdSet": 1, "cmdId": 1},      # Basic Info
                        ]
                        
                        for i, params in enumerate(standard_requests):
                            thing_topic = f"/app/{self.username}/{device_sn}/thing/property/get"
                            thing_payload = {
                                "id": self.get_next_message_id(),
                                "version": "1.0",
                                "params": params,
                                "timestamp": int(time.time() * 1000)
                            }
                            
                            result = mqtt_client.publish(thing_topic, json.dumps(thing_payload), qos=1)
                            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                                simulation_success += 1
                                _LOGGER.info(f"Standard request {i+1}/3 sent for {device_sn}")
                            total_attempts += 1
                            
                            await asyncio.sleep(0.8)
                            
                        _LOGGER.info(f"Standard parameters used for {device_sn}")
                    
                    # === Phase 4: Abschließende Status-Abfrage ===
                    status_topic = f"/app/device/property/{device_sn}/get"
                    status_payload = {
                        "id": self.get_next_message_id(),
                        "version": "1.0",
                        "params": {"quotaMap": 0},  # Status ohne Quota
                        "timestamp": int(time.time() * 1000)
                    }
                    result = mqtt_client.publish(status_topic, json.dumps(status_payload), qos=1)
                    if result.rc == mqtt.MQTT_ERR_SUCCESS:
                        simulation_success += 1
                        _LOGGER.info(f"Final status request sent for {device_sn}")
                    total_attempts += 1
                    
                    await asyncio.sleep(2.0)  # Längere Pause zwischen Geräten
                    
                except Exception as device_error:
                    _LOGGER.warning(f"App simulation failed for device {device_sn}: {device_error}")
            
            # === Phase 5: Zusätzliche Stream Ultra Wakeup Sequence ===
            await self.send_stream_ultra_wakeup_sequence()
            
            # === Phase 6: API-Level Device Activation ===
            await self.send_api_device_activation()
            
            success_rate = simulation_success / total_attempts if total_attempts > 0 else 0
            _LOGGER.info(f"Enhanced app simulation completed: {simulation_success}/{total_attempts} messages sent successfully ({success_rate:.1%})")
            
            # === Phase 6: Warte auf erste Antworten ===
            _LOGGER.info("Waiting 10 seconds for device responses...")
            await asyncio.sleep(10)
            
            # Prüfe ob Nachrichten angekommen sind
            if hasattr(self, 'message_count') and self.message_count > 0:
                _LOGGER.info(f"Success! Received {self.message_count} messages after app simulation")
                return True
            else:
                _LOGGER.warning("No messages received yet - triggering deep sleep recovery")
                
                # === Phase 7: Deep Sleep Recovery als Fallback ===
                _LOGGER.info("Starting deep sleep recovery protocol...")
                deep_sleep_success = await self.send_deep_sleep_wakeup_protocol()
                
                # Warte nochmal auf Antworten nach Deep Sleep Recovery
                await asyncio.sleep(15)
                
                if hasattr(self, 'message_count') and self.message_count > 0:
                    _LOGGER.info(f"SUCCESS! Deep sleep recovery activated device - received {self.message_count} messages")
                    return True
                elif deep_sleep_success:
                    _LOGGER.info("Deep sleep recovery completed successfully but no immediate messages")
                    return True
                else:
                    _LOGGER.warning("Enhanced app simulation and deep sleep recovery completed - may need manual intervention")
                    return success_rate > 0.7  # Erfolg wenn mehr als 70% der Nachrichten erfolgreich
            
        except Exception as e:
            _LOGGER.error(f"Enhanced app simulation failed: {e}")
            return False

    async def send_stream_ultra_wakeup_sequence(self):
        """
        Erweiterte Stream Ultra Wakeup-Sequenz mit Deep Sleep Recovery
        Kombiniert normale Wakeup-Sequenz mit intensiver Deep Sleep Recovery
        """
        if not self.api_client:
            return
            
        try:
            mqtt_client = self.get_ecoflow_mqtt_client()
            if not mqtt_client:
                return
                
            # Suche nach Stream Ultra Geräten
            stream_devices = []
            for device_sn in self.device_sns:
                device_type = self.detect_device_type(device_sn).lower()
                if 'stream' in device_type or 'ultra' in device_type:
                    stream_devices.append(device_sn)
            
            if not stream_devices:
                return
                
            _LOGGER.info(f"Sending enhanced Stream Ultra wakeup sequence for {len(stream_devices)} devices...")
            
            for device_sn in stream_devices:
                # Phase 1: App Connection Simulation (Deep Sleep Recovery)
                _LOGGER.info(f"Starting deep sleep recovery for {device_sn}")
                
                app_connect_messages = [
                    {
                        "topic": f"/app/device/heartbeat/{device_sn}",
                        "payload": {
                            "id": self.get_next_message_id(),
                            "version": "1.0",
                            "timestamp": int(time.time() * 1000),
                            "src": 32,
                            "dest": 53,
                            "deviceSn": device_sn,
                            "params": {"heartbeat": 1}
                        }
                    },
                    {
                        "topic": f"/app/device/connect/{device_sn}",
                        "payload": {
                            "id": self.get_next_message_id(),
                            "version": "1.0", 
                            "timestamp": int(time.time() * 1000),
                            "src": 32,
                            "dest": 53,
                            "deviceSn": device_sn,
                            "params": {"connect": 1}
                        }
                    }
                ]
                
                for msg in app_connect_messages:
                    try:
                        result = mqtt_client.publish(msg["topic"], json.dumps(msg["payload"]), qos=1)
                        if result.rc == mqtt.MQTT_ERR_SUCCESS:
                            _LOGGER.info(f"App connection signal sent: {msg['topic']}")
                        await asyncio.sleep(0.5)
                    except Exception as e:
                        _LOGGER.debug(f"App connection failed: {e}")
                
                # Phase 2: Device Discovery/Ping
                discovery_topics = [
                    f"/ping/{device_sn}",
                    f"/discover/{device_sn}", 
                    f"/app/ping/{device_sn}",
                    f"/app/discover/{device_sn}"
                ]
                
                ping_payload = {
                    "id": self.get_next_message_id(),
                    "version": "1.0",
                    "timestamp": int(time.time() * 1000),
                    "params": {"ping": 1}
                }
                
                for topic in discovery_topics:
                    try:
                        result = mqtt_client.publish(topic, json.dumps(ping_payload), qos=1)
                        if result.rc == mqtt.MQTT_ERR_SUCCESS:
                            _LOGGER.info(f"Device discovery ping sent: {topic}")
                        await asyncio.sleep(0.3)
                    except Exception as e:
                        _LOGGER.debug(f"Discovery ping failed: {e}")
                
                # Phase 3: Stream Ultra Power Management Wake-up
                power_wakeup_commands = [
                    # System Power Management
                    {"cmdSet": 1, "cmdId": 1, "params": {"sys_power_on": 1}},
                    {"cmdSet": 1, "cmdId": 2, "params": {"sys_wakeup": 1}},
                    {"cmdSet": 1, "cmdId": 254, "params": {"sys_enable_all": 1}},
                    
                    # Battery Management System
                    {"cmdSet": 2, "cmdId": 1, "params": {"bms_wakeup": 1}},
                    {"cmdSet": 2, "cmdId": 2, "params": {"bms_enable": 1}},
                    
                    # Inverter Management
                    {"cmdSet": 3, "cmdId": 1, "params": {"inv_enable": 1}},
                    {"cmdSet": 3, "cmdId": 254, "params": {"inv_wakeup": 1}},
                ]
                
                for i, cmd in enumerate(power_wakeup_commands):
                    wakeup_topic = f"/app/{self.username}/{device_sn}/thing/property/set"
                    wakeup_payload = {
                        "id": self.get_next_message_id(),
                        "version": "1.0",
                        "timestamp": int(time.time() * 1000),
                        "src": 32,
                        "dest": 53,
                        "deviceSn": device_sn,
                        "params": cmd
                    }
                    
                    try:
                        result = mqtt_client.publish(wakeup_topic, json.dumps(wakeup_payload), qos=1)
                        if result.rc == mqtt.MQTT_ERR_SUCCESS:
                            _LOGGER.info(f"Stream Ultra power wakeup {i+1}/7 sent (cmdSet: {cmd['cmdSet']}, cmdId: {cmd['cmdId']})")
                        await asyncio.sleep(0.5)
                    except Exception as e:
                        _LOGGER.debug(f"Power wakeup command failed: {e}")
                
                # Phase 4: Communication Wake-up
                comm_wakeup_commands = [
                    {"cmdSet": 20, "cmdId": 1, "params": {"comm_enable": 1}},
                    {"cmdSet": 20, "cmdId": 2, "params": {"data_transmission_enable": 1}},
                    {"cmdSet": 11, "cmdId": 1, "params": {"ac_out_enable": 1}},
                    {"cmdSet": 12, "cmdId": 1, "params": {"dc_out_enable": 1}},
                ]
                
                for i, cmd in enumerate(comm_wakeup_commands):
                    wakeup_topic = f"/app/{self.username}/{device_sn}/thing/property/set"
                    wakeup_payload = {
                        "id": self.get_next_message_id(),
                        "version": "1.0",
                        "timestamp": int(time.time() * 1000),
                        "src": 32,
                        "dest": 53,
                        "deviceSn": device_sn,
                        "params": cmd
                    }
                    
                    try:
                        result = mqtt_client.publish(wakeup_topic, json.dumps(wakeup_payload), qos=1)
                        if result.rc == mqtt.MQTT_ERR_SUCCESS:
                            _LOGGER.info(f"Stream Ultra comm wakeup {i+1}/4 sent (cmdSet: {cmd['cmdSet']}, cmdId: {cmd['cmdId']})")
                        await asyncio.sleep(0.4)
                    except Exception as e:
                        _LOGGER.debug(f"Comm wakeup command failed: {e}")
                
                # Phase 5: Status Request Bombardment
                status_request_commands = [
                    {"cmdSet": 0, "cmdId": 1},      # General Status
                    {"cmdSet": 0, "cmdId": 254},    # All Status
                    {"cmdSet": 1, "cmdId": 1},      # System Status
                    {"cmdSet": 2, "cmdId": 1},      # Battery Status
                    {"cmdSet": 3, "cmdId": 1},      # Inverter Status
                    {"cmdSet": 11, "cmdId": 1},     # AC Status
                    {"cmdSet": 20, "cmdId": 1},     # Communication Status
                ]
                
                for i, cmd in enumerate(status_request_commands):
                    status_topic = f"/app/{self.username}/{device_sn}/thing/property/get"
                    status_payload = {
                        "id": self.get_next_message_id(),
                        "version": "1.0",
                        "timestamp": int(time.time() * 1000),
                        "src": 32,
                        "dest": 53,
                        "deviceSn": device_sn,
                        "params": cmd
                    }
                    
                    try:
                        result = mqtt_client.publish(status_topic, json.dumps(status_payload), qos=1)
                        if result.rc == mqtt.MQTT_ERR_SUCCESS:
                            _LOGGER.info(f"Stream Ultra status request {i+1}/7 sent (cmdSet: {cmd['cmdSet']}, cmdId: {cmd['cmdId']})")
                        await asyncio.sleep(0.3)
                    except Exception as e:
                        _LOGGER.debug(f"Status request failed: {e}")
                
                # Phase 6: Alternative Topic Wake-up
                alternative_topics = [
                    f"/stream/{device_sn}/wakeup",
                    f"/ultra/{device_sn}/activate",
                    f"/device/{device_sn}/stream/enable",
                ]
                
                wakeup_payload = {
                    "id": self.get_next_message_id(),
                    "version": "1.0",
                    "timestamp": int(time.time() * 1000),
                    "params": {"wakeup": 1, "force": 1, "stream_ultra": 1}
                }
                
                for topic in alternative_topics:
                    try:
                        result = mqtt_client.publish(topic, json.dumps(wakeup_payload), qos=1)
                        if result.rc == mqtt.MQTT_ERR_SUCCESS:
                            _LOGGER.info(f"Stream Ultra alternative topic sent: {topic}")
                        await asyncio.sleep(0.2)
                    except Exception as e:
                        _LOGGER.debug(f"Alternative topic failed: {e}")
                
                # Phase 7: Heartbeat Simulation
                heartbeat_topics = [
                    f"/app/{self.username}/{device_sn}/heartbeat",
                    f"/app/device/{device_sn}/heartbeat",
                ]
                
                heartbeat_payload = {
                    "id": self.get_next_message_id(),
                    "version": "1.0",
                    "timestamp": int(time.time() * 1000),
                    "params": {
                        "heartbeat": 1,
                        "app_active": 1,
                        "stream_ultra_session": int(time.time())
                    }
                }
                
                for topic in heartbeat_topics:
                    try:
                        result = mqtt_client.publish(topic, json.dumps(heartbeat_payload), qos=1)
                        if result.rc == mqtt.MQTT_ERR_SUCCESS:
                            _LOGGER.info(f"Stream Ultra heartbeat sent: {topic}")
                        await asyncio.sleep(0.2)
                    except Exception as e:
                        _LOGGER.debug(f"Heartbeat failed: {e}")
                
                _LOGGER.info(f"Complete Stream Ultra deep sleep wakeup sequence sent for {device_sn}")
                
        except Exception as e:
            _LOGGER.warning(f"Stream Ultra wakeup sequence error: {e}")

    async def send_api_device_activation(self):
        """
        API-Level Device Activation - direkte API-Calls um Geräte zu aktivieren
        Dies ergänzt die MQTT-basierten Nachrichten
        """
        try:
            _LOGGER.info("Starting API-level device activation...")
            
            for device_sn in self.device_sns:
                try:
                    # API Quota Call für jedes Gerät
                    if hasattr(self.api_client, 'get_device_quota'):
                        await self.api_client.get_device_quota(device_sn)
                        _LOGGER.info(f"API quota call sent for {device_sn}")
                        await asyncio.sleep(1)
                    
                    # API Property Call 
                    if hasattr(self.api_client, 'get_device_info'):
                        await self.api_client.get_device_info(device_sn)
                        _LOGGER.info(f"API device info call sent for {device_sn}")
                        await asyncio.sleep(1)
                        
                    # Generischer API Call falls spezifische nicht verfügbar
                    if hasattr(self.api_client, 'quota_all'):
                        await self.api_client.quota_all(None)
                        _LOGGER.info(f"API quota_all call sent")
                        break  # Nur einmal für alle Geräte
                        
                except Exception as device_api_error:
                    _LOGGER.debug(f"API activation for {device_sn} failed: {device_api_error}")
                    
            _LOGGER.info("API-level device activation completed")
            
        except Exception as e:
            _LOGGER.debug(f"API device activation error: {e}")

    async def send_persistent_activation_attempts(self, max_attempts=5):
        """
        Persistente Aktivierungsversuche für schlafende Stream Ultra Geräte
        Kombiniert normale Wakeup-Sequenz mit Deep Sleep Recovery
        """
        try:
            _LOGGER.info(f"Starting persistent activation attempts (max {max_attempts})...")
            
            for attempt in range(max_attempts):
                _LOGGER.info(f"Activation attempt {attempt + 1}/{max_attempts}")
                
                # Strategy 1: Enhanced App Simulation
                initial_count = getattr(self, 'message_count', 0)
                await self.send_enhanced_app_simulation()
                await asyncio.sleep(5)
                
                # Check for messages
                current_count = getattr(self, 'message_count', 0)
                if current_count > initial_count:
                    new_messages = current_count - initial_count
                    _LOGGER.info(f"SUCCESS! Got {new_messages} messages on attempt {attempt + 1}")
                    return True
                
                # Strategy 2: Deep Sleep Wake-up Protocol
                await self.send_deep_sleep_wakeup_protocol()
                await asyncio.sleep(8)
                
                # Check again
                current_count = getattr(self, 'message_count', 0)
                if current_count > initial_count:
                    new_messages = current_count - initial_count
                    _LOGGER.info(f"SUCCESS! Got {new_messages} messages with deep sleep wakeup")
                    return True
                
                # Strategy 3: Alternative MQTT topics
                await self.send_alternative_activation_messages()
                await asyncio.sleep(5)
                
                # Check again
                current_count = getattr(self, 'message_count', 0)
                if current_count > initial_count:
                    new_messages = current_count - initial_count
                    _LOGGER.info(f"SUCCESS! Got {new_messages} messages with alternative topics")
                    return True
                
                # Strategy 4: Power Cycle Simulation (for Stream Ultra)
                await self.send_stream_ultra_power_cycle_simulation()
                await asyncio.sleep(5)
                
                # Check again
                current_count = getattr(self, 'message_count', 0)
                if current_count > initial_count:
                    new_messages = current_count - initial_count
                    _LOGGER.info(f"SUCCESS! Got {new_messages} messages with power cycle simulation")
                    return True
                
                # Strategy 5: Intensive API calls
                await self.send_intensive_api_activation()
                await asyncio.sleep(10)  # Longer wait for API responses
                
                # Final check
                current_count = getattr(self, 'message_count', 0)
                if current_count > initial_count:
                    new_messages = current_count - initial_count
                    _LOGGER.info(f"SUCCESS! Got {new_messages} messages with API activation")
                    return True
                
                _LOGGER.warning(f"Attempt {attempt + 1} failed - no messages received")
                if attempt < max_attempts - 1:
                    _LOGGER.info("Waiting 15 seconds before next attempt...")
                    await asyncio.sleep(15)
            
            _LOGGER.warning(f"All {max_attempts} activation attempts failed")
            _LOGGER.info("Manual intervention recommended: Open EcoFlow app or press device power button")
            return False
            
        except Exception as e:
            _LOGGER.error(f"Persistent activation attempts failed: {e}")
            return False

    async def send_alternative_activation_messages(self):
        """
        Alternative MQTT topics and message formats based on other implementations
        """
        try:
            mqtt_client = self.get_ecoflow_mqtt_client()
            if not mqtt_client:
                return
                
            _LOGGER.info("Sending alternative activation messages...")
            
            for device_sn in self.device_sns:
                # Alternative topic structures seen in other implementations
                alternative_messages = [
                    # Topic variation 1
                    {
                        "topic": f"/topic/device/{device_sn}/quota",
                        "payload": {
                            "id": self.get_next_message_id(),
                            "version": "1.0",
                            "params": {},
                            "timestamp": int(time.time() * 1000)
                        }
                    },
                    # Topic variation 2  
                    {
                        "topic": f"/topic/{device_sn}/property/get",
                        "payload": {
                            "id": self.get_next_message_id(),
                            "version": "1.0", 
                            "params": {"quotaMap": 1},
                            "timestamp": int(time.time() * 1000)
                        }
                    },
                    # Direct device topic
                    {
                        "topic": f"/{device_sn}/property/get",
                        "payload": {
                            "id": self.get_next_message_id(),
                            "version": "1.0",
                            "params": {"quotaMap": 1},
                            "timestamp": int(time.time() * 1000)
                        }
                    }
                ]
                
                for i, msg in enumerate(alternative_messages):
                    result = mqtt_client.publish(msg["topic"], json.dumps(msg["payload"]), qos=1)
                    if result.rc == mqtt.MQTT_ERR_SUCCESS:
                        _LOGGER.info(f"Alternative message {i+1}/3 sent to {msg['topic']}")
                    await asyncio.sleep(1)
                    
        except Exception as e:
            _LOGGER.debug(f"Alternative activation messages error: {e}")

    async def send_intensive_api_activation(self):
        """
        Intensive API-based activation with multiple calls
        """
        try:
            _LOGGER.info("Starting intensive API activation...")
            
            # Multiple API calls in sequence
            api_calls = [
                "quota_all",
                "get_device_quota", 
                "get_device_info",
                "get_device_list"
            ]
            
            for call_name in api_calls:
                try:
                    if hasattr(self.api_client, call_name):
                        method = getattr(self.api_client, call_name)
                        if call_name in ["get_device_quota", "get_device_info"]:
                            # Device-specific calls
                            for device_sn in self.device_sns:
                                await method(device_sn)
                                _LOGGER.info(f"API {call_name} called for {device_sn}")
                                await asyncio.sleep(1)
                        else:
                            # Global calls
                            await method(None)
                            _LOGGER.info(f"API {call_name} called")
                            await asyncio.sleep(1)
                except Exception as api_error:
                    _LOGGER.debug(f"API call {call_name} failed: {api_error}")
                    
        except Exception as e:
            _LOGGER.debug(f"Intensive API activation error: {e}")

    async def send_deep_sleep_wakeup_protocol(self):
        """
        Deep Sleep Wake-up Protocol für alle EcoFlow Geräte
        Kombiniert App Connection Simulation mit intensiven Wake-up Commands
        """
        if not self.api_client:
            return False
            
        try:
            mqtt_client = self.get_ecoflow_mqtt_client()
            if not mqtt_client:
                _LOGGER.warning("No MQTT client for deep sleep wakeup")
                return False
                
            _LOGGER.info("Starting deep sleep wakeup protocol...")
            
            success_count = 0
            total_attempts = 0
            
            for device_sn in self.device_sns:
                device_type = self.detect_device_type(device_sn)
                _LOGGER.info(f"Deep sleep wakeup for {device_type}: {device_sn}")
                
                # Phase 1: App Connection Simulation
                app_connect_messages = [
                    {
                        "topic": f"/app/device/heartbeat/{device_sn}",
                        "payload": {
                            "id": self.get_next_message_id(),
                            "version": "1.0",
                            "timestamp": int(time.time() * 1000),
                            "src": 32,
                            "dest": 53,
                            "deviceSn": device_sn,
                            "params": {"heartbeat": 1}
                        }
                    },
                    {
                        "topic": f"/app/device/connect/{device_sn}",
                        "payload": {
                            "id": self.get_next_message_id(),
                            "version": "1.0", 
                            "timestamp": int(time.time() * 1000),
                            "src": 32,
                            "dest": 53,
                            "deviceSn": device_sn,
                            "params": {"connect": 1}
                        }
                    }
                ]
                
                for msg in app_connect_messages:
                    try:
                        result = mqtt_client.publish(msg["topic"], json.dumps(msg["payload"]), qos=1)
                        if result.rc == mqtt.MQTT_ERR_SUCCESS:
                            success_count += 1
                            _LOGGER.info(f"App connection signal sent: {msg['topic']}")
                        total_attempts += 1
                        await asyncio.sleep(0.5)
                    except Exception as e:
                        _LOGGER.debug(f"App connection failed: {e}")
                        
                # Phase 2: Device Discovery/Ping
                discovery_topics = [
                    f"/ping/{device_sn}",
                    f"/discover/{device_sn}", 
                    f"/app/ping/{device_sn}",
                    f"/app/discover/{device_sn}"
                ]
                
                ping_payload = {
                    "id": self.get_next_message_id(),
                    "version": "1.0",
                    "timestamp": int(time.time() * 1000),
                    "params": {"ping": 1}
                }
                
                for topic in discovery_topics:
                    try:
                        result = mqtt_client.publish(topic, json.dumps(ping_payload), qos=1)
                        if result.rc == mqtt.MQTT_ERR_SUCCESS:
                            success_count += 1
                            _LOGGER.info(f"Device discovery ping sent: {topic}")
                        total_attempts += 1
                        await asyncio.sleep(0.3)
                    except Exception as e:
                        _LOGGER.debug(f"Discovery ping failed: {e}")
                
                # Phase 3: Device-specific Wake-up Commands
                if "stream" in device_type.lower() or "ultra" in device_type.lower():
                    # Stream Ultra spezifische Commands
                    await self._send_stream_ultra_deep_sleep_commands(device_sn, mqtt_client)
                else:
                    # Standard EcoFlow Geräte Commands
                    await self._send_standard_deep_sleep_commands(device_sn, mqtt_client)
                
                # Phase 4: Data Request Bombardment
                data_request_topics = [
                    f"/app/device/property/{device_sn}",
                    f"/app/device/property/{device_sn}/get", 
                    f"/app/device/quota/{device_sn}",
                    f"/topic/device/{device_sn}/thing/property/get",
                    f"/app/{self.username}/{device_sn}/thing/property/get"
                ]
                
                for topic in data_request_topics:
                    data_payload = {
                        "id": self.get_next_message_id(),
                        "version": "1.0",
                        "timestamp": int(time.time() * 1000),
                        "params": {"quotaMap": 1, "force": 1}
                    }
                    
                    try:
                        result = mqtt_client.publish(topic, json.dumps(data_payload), qos=1)
                        if result.rc == mqtt.MQTT_ERR_SUCCESS:
                            success_count += 1
                            _LOGGER.info(f"Data request sent: {topic}")
                        total_attempts += 1
                        await asyncio.sleep(0.4)
                    except Exception as e:
                        _LOGGER.debug(f"Data request failed: {e}")
                
            success_rate = success_count / total_attempts if total_attempts > 0 else 0
            _LOGGER.info(f"Deep sleep wakeup protocol completed: {success_count}/{total_attempts} messages sent ({success_rate:.1%})")
            
            return success_rate > 0.8
            
        except Exception as e:
            _LOGGER.error(f"Deep sleep wakeup protocol failed: {e}")
            return False

    async def _send_stream_ultra_deep_sleep_commands(self, device_sn: str, mqtt_client):
        """Stream Ultra spezifische Deep Sleep Wake-up Commands"""
        try:
            commands = [
                # Power Management Wake-up
                {"cmdSet": 1, "cmdId": 1, "params": {"sys_power_on": 1}},
                {"cmdSet": 1, "cmdId": 2, "params": {"sys_wakeup": 1}},
                {"cmdSet": 1, "cmdId": 254, "params": {"sys_enable_all": 1}},
                
                # Battery Management System
                {"cmdSet": 2, "cmdId": 1, "params": {"bms_wakeup": 1}},
                {"cmdSet": 2, "cmdId": 254, "params": {"bms_enable": 1}},
                
                # Inverter Management
                {"cmdSet": 3, "cmdId": 1, "params": {"inv_enable": 1}},
                {"cmdSet": 3, "cmdId": 254, "params": {"inv_wakeup": 1}},
                
                # Communication System
                {"cmdSet": 20, "cmdId": 1, "params": {"comm_enable": 1}},
                {"cmdSet": 20, "cmdId": 2, "params": {"data_enable": 1}},
                
                # AC/DC Control
                {"cmdSet": 11, "cmdId": 1, "params": {"ac_enable": 1}},
                {"cmdSet": 12, "cmdId": 1, "params": {"dc_enable": 1}},
                
                # Status Request Commands
                {"cmdSet": 0, "cmdId": 1, "params": {"get_status": 1}},
                {"cmdSet": 0, "cmdId": 254, "params": {"get_all": 1}}
            ]
            
            for i, cmd in enumerate(commands):
                topic = f"/app/{self.username}/{device_sn}/thing/property/set"
                payload = {
                    "id": self.get_next_message_id(),
                    "version": "1.0",
                    "timestamp": int(time.time() * 1000),
                    "src": 32,
                    "dest": 53, 
                    "deviceSn": device_sn,
                    "params": cmd
                }
                
                try:
                    result = mqtt_client.publish(topic, json.dumps(payload), qos=1)
                    if result.rc == mqtt.MQTT_ERR_SUCCESS:
                        _LOGGER.info(f"Stream Ultra deep sleep command {i+1}/13 sent (cmdSet: {cmd['cmdSet']}, cmdId: {cmd['cmdId']})")
                    await asyncio.sleep(0.8)
                except Exception as e:
                    _LOGGER.debug(f"Stream Ultra deep sleep command failed: {e}")
                    
        except Exception as e:
            _LOGGER.debug(f"Stream Ultra deep sleep commands error: {e}")

    async def _send_standard_deep_sleep_commands(self, device_sn: str, mqtt_client):
        """Standard EcoFlow Geräte Deep Sleep Wake-up Commands"""
        try:
            commands = [
                # Standard Power Wake-up
                {"cmdSet": 1, "cmdId": 1, "params": {"power_on": 1}},
                {"cmdSet": 1, "cmdId": 254, "params": {"enable_all": 1}},
                
                # Battery System
                {"cmdSet": 2, "cmdId": 1, "params": {"bms_enable": 1}},
                
                # Status Requests
                {"cmdSet": 0, "cmdId": 1, "params": {"get_status": 1}},
                {"cmdSet": 20, "cmdId": 1, "params": {"comm_enable": 1}},
            ]
            
            for i, cmd in enumerate(commands):
                topic = f"/app/{self.username}/{device_sn}/thing/property/set"
                payload = {
                    "id": self.get_next_message_id(),
                    "version": "1.0",
                    "timestamp": int(time.time() * 1000),
                    "src": 32,
                    "dest": 53, 
                    "deviceSn": device_sn,
                    "params": cmd
                }
                
                try:
                    result = mqtt_client.publish(topic, json.dumps(payload), qos=1)
                    if result.rc == mqtt.MQTT_ERR_SUCCESS:
                        _LOGGER.info(f"Standard deep sleep command {i+1}/5 sent (cmdSet: {cmd['cmdSet']}, cmdId: {cmd['cmdId']})")
                    await asyncio.sleep(0.6)
                except Exception as e:
                    _LOGGER.debug(f"Standard deep sleep command failed: {e}")
                    
        except Exception as e:
            _LOGGER.debug(f"Standard deep sleep commands error: {e}")

    async def send_stream_ultra_power_cycle_simulation(self):
        """
        Simuliert Power Cycle für Stream Ultra (An/Aus/An Sequenz)
        """
        try:
            mqtt_client = self.get_ecoflow_mqtt_client()
            if not mqtt_client:
                return False
                
            _LOGGER.info("Starting Stream Ultra power cycle simulation...")
            
            for device_sn in self.device_sns:
                device_type = self.detect_device_type(device_sn)
                if not ("stream" in device_type.lower() or "ultra" in device_type.lower()):
                    continue
                    
                # Power Cycle Sequenz: OFF -> Wait -> ON -> Wait -> ENABLE
                power_cycle_sequence = [
                    # 1. Soft Power Off
                    {"cmdSet": 1, "cmdId": 2, "params": {"sys_power_off": 0}},
                    # 2. Power On
                    {"cmdSet": 1, "cmdId": 1, "params": {"sys_power_on": 1}},
                    # 3. Enable All Systems
                    {"cmdSet": 1, "cmdId": 254, "params": {"sys_enable_all": 1}},
                    # 4. Enable Inverter
                    {"cmdSet": 3, "cmdId": 1, "params": {"inv_enable": 1}},
                    # 5. Enable Communication
                    {"cmdSet": 20, "cmdId": 1, "params": {"comm_enable": 1}}
                ]
                
                for i, cmd in enumerate(power_cycle_sequence):
                    topic = f"/app/{self.username}/{device_sn}/thing/property/set"
                    payload = {
                        "id": self.get_next_message_id(),
                        "version": "1.0",
                        "timestamp": int(time.time() * 1000),
                        "src": 32,
                        "dest": 53,
                        "deviceSn": device_sn,
                        "params": cmd
                    }
                    
                    try:
                        result = mqtt_client.publish(topic, json.dumps(payload), qos=1)
                        if result.rc == mqtt.MQTT_ERR_SUCCESS:
                            _LOGGER.info(f"Stream Ultra power cycle step {i+1}/5 sent (cmdSet: {cmd['cmdSet']}, cmdId: {cmd['cmdId']})")
                        
                        # Spezielle Wartezeiten für Power Cycle
                        if i == 0:  # Nach Power Off
                            await asyncio.sleep(3)
                        elif i == 2:  # Nach Power On
                            await asyncio.sleep(2)
                        else:
                            await asyncio.sleep(1)
                            
                    except Exception as e:
                        _LOGGER.debug(f"Power cycle step failed: {e}")
                        
            _LOGGER.info("Stream Ultra power cycle simulation completed")
            return True
            
        except Exception as e:
            _LOGGER.warning(f"Stream Ultra power cycle simulation failed: {e}")
            return False

    def get_next_message_id(self):
        """Generiert eine eindeutige Message ID"""
        if not hasattr(self, '_message_id_counter'):
            self._message_id_counter = 100
        self._message_id_counter += 1
        return self._message_id_counter

    async def gentle_connection_recovery(self):
        """Sanfte Verbindungswiederherstellung ohne aggressive Disconnects"""
        try:
            _LOGGER.info("Initiating gentle connection recovery...")
            
            mqtt_client = self.get_ecoflow_mqtt_client()
            if not mqtt_client:
                _LOGGER.warning("No MQTT client available for recovery")
                return
                
            # Prüfe aktuelle Verbindung
            if mqtt_client.is_connected():
                # Versuche sanfte Wiederherstellung über Ping
                try:
                    if hasattr(mqtt_client, 'ping'):
                        mqtt_client.ping()
                        _LOGGER.info("MQTT ping sent for connection recovery")
                    
                    # Kurz warten für Antwort
                    await asyncio.sleep(2)
                    
                    # Prüfe ob Verbindung nun stabil ist
                    if await self.check_mqtt_connection_health(mqtt_client):
                        _LOGGER.info("Gentle recovery successful - connection restored")
                        # Nach erfolgreicher Verbindung: Enhanced App Simulation
                        await self.send_enhanced_app_simulation()
                        return
                        
                except Exception as ping_error:
                    _LOGGER.debug(f"MQTT ping failed: {ping_error}")
            
            # Falls sanfte Methode fehlschlägt, versuche Neuverbindung über API Client
            _LOGGER.info("Attempting API client restart...")
            try:
                if hasattr(self.api_client, 'stop'):
                    self.api_client.stop()
                    await asyncio.sleep(3)
                    
                if hasattr(self.api_client, 'start'):
                    loop = asyncio.get_running_loop()
                    await loop.run_in_executor(None, self.api_client.start)
                    _LOGGER.info("API client restart completed")
                    
                    # Warte kurz und prüfe ob Reconnect erfolgreich war
                    await asyncio.sleep(5)
                    
                    # Prüfe finale Verbindung
                    updated_client = self.get_ecoflow_mqtt_client()
                    if updated_client and updated_client.is_connected():
                        _LOGGER.info("API client restart successful - MQTT reconnected")
                        # Setze Zeitstempel für Health Check
                        if hasattr(updated_client, '_last_msg_in'):
                            updated_client._last_msg_in = time.time()
                        
                        # Nach erfolgreicher Reconnection: Enhanced App Simulation
                        await asyncio.sleep(2)  # Kurz warten für Stabilisierung
                        await self.send_enhanced_app_simulation()
                        return
                    else:
                        _LOGGER.warning("API client restart completed but MQTT not connected")
                    
            except Exception as restart_error:
                _LOGGER.error(f"API client restart failed: {restart_error}")
                
        except Exception as e:
            _LOGGER.error(f"Gentle connection recovery failed: {e}")

    async def send_heartbeat_messages(self):
        """
        Natürliche Heartbeat-Nachrichten wie echte EcoFlow App
        Rotiert zwischen verschiedenen Message-Typen statt alle gleichzeitig zu senden
        """
        if not self.api_client:
            return
            
        try:
            mqtt_client = self.get_ecoflow_mqtt_client()
            if not mqtt_client:
                _LOGGER.debug("No MQTT client available for heartbeat")
                return
                
            if not mqtt_client.is_connected():
                _LOGGER.debug("MQTT not connected for heartbeat")
                return
            
            # Natürliche App-ähnliche Heartbeat-Rotation für alle EcoFlow Geräte
            heartbeat_sent = False
            
            # Smart Rotation: Nur eine Nachricht pro Heartbeat (wie echte App)
            if not hasattr(self, 'heartbeat_rotation_index'):
                self.heartbeat_rotation_index = 0
            
            for device_sn in self.device_sns:
                try:
                    current_time = int(time.time() * 1000)
                    device_type = self.detect_device_type(device_sn)
                    
                    # Stream Ultra-optimierte Heartbeat-Rotation
                    if device_type in ["STREAM_ULTRA", "STREAM_AC", "STREAM_PRO"]:
                        if self.heartbeat_rotation_index % 3 == 0:
                            # Stream Ultra Quota mit erweiterten Parametern
                            topic = f"/app/device/quota/{device_sn}"
                            payload = {
                                "id": current_time % 1000,
                                "version": "1.0", 
                                "params": {
                                    "typeMap": 1,
                                    "quotaMap": 1
                                },
                                "timestamp": current_time
                            }
                            heartbeat_type = "quota"
                        elif self.heartbeat_rotation_index % 3 == 1:
                            # Stream Ultra Property mit allen Datentypen
                            topic = f"/app/device/property/{device_sn}/get"
                            payload = {
                                "id": (current_time + 1) % 1000,
                                "version": "1.0",
                                "params": {
                                    "quotaMap": 1,
                                    "streamData": 1,
                                    "batteryData": 1,
                                    "realTimeData": 1
                                },
                                "timestamp": current_time
                            }
                            heartbeat_type = "property"
                        else:
                            # Stream Ultra Thing mit korrektem cmdSet
                            topic = f"/app/{self.username}/{device_sn}/thing/property/get"
                            payload = {
                                "id": (current_time + 2) % 1000,
                                "version": "1.0",
                                "params": {
                                    "cmdSet": 3,
                                    "cmdId": 254,
                                    "dataType": 0
                                },
                                "timestamp": current_time
                            }
                            heartbeat_type = "thing"
                    else:
                        # Standard Heartbeat für andere Geräte
                        if self.heartbeat_rotation_index % 3 == 0:
                            topic = f"/app/device/quota/{device_sn}"
                            payload = {
                                "id": 102,
                                "version": "1.0",
                                "params": {},
                                "timestamp": current_time
                            }
                            heartbeat_type = "quota"
                        elif self.heartbeat_rotation_index % 3 == 1:
                            topic = f"/app/device/property/{device_sn}/get"
                            payload = {
                                "id": 103,
                                "version": "1.0", 
                                "params": {"quotaMap": 1},
                                "timestamp": current_time
                            }
                            heartbeat_type = "property"
                        else:
                            topic = f"/app/{self.username}/{device_sn}/thing/property/get"
                            payload = {
                                "id": 104,
                                "version": "1.0",
                                "params": {"cmdSet": 20, "cmdId": 1},
                                "timestamp": current_time
                            }
                            heartbeat_type = "thing"
                    
                    # Sende nur eine Nachricht (natürlich)
                    result = mqtt_client.publish(topic, json.dumps(payload), qos=1)
                    
                    if result.rc == mqtt.MQTT_ERR_SUCCESS:
                        heartbeat_sent = True
                        _LOGGER.debug(f"Natural {heartbeat_type} heartbeat sent for {device_sn}")
                    else:
                        _LOGGER.debug(f"Heartbeat failed for {device_sn}: rc={result.rc}")
                        
                except Exception as device_error:
                    _LOGGER.debug(f"Heartbeat failed for {device_sn}: {device_error}")
                    continue
            
            # Erhöhe Rotation für nächsten Heartbeat
            self.heartbeat_rotation_index += 1
            
            # Gelegentliches MQTT-Ping (nur alle 10 Heartbeats für natürliches Verhalten)
            if self.heartbeat_rotation_index % 10 == 0:
                try:
                    if hasattr(mqtt_client, 'ping'):
                        mqtt_client.ping()
                        _LOGGER.debug("Natural MQTT ping sent")
                        heartbeat_sent = True
                except Exception as ping_error:
                    _LOGGER.debug(f"Natural MQTT ping failed: {ping_error}")
            
            # Update Message-Timestamps für Health-Check
            if heartbeat_sent:
                try:
                    current_time = time.time()
                    if hasattr(mqtt_client, '_last_msg_out'):
                        mqtt_client._last_msg_out = current_time
                        _LOGGER.debug("Updated _last_msg_out timestamp")
                except Exception as timestamp_error:
                    _LOGGER.debug(f"Failed to update message timestamp: {timestamp_error}")
                    
        except Exception as e:
            _LOGGER.debug(f"Heartbeat system error: {e}")

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
            _LOGGER.info("Waiting for EcoFlow MQTT connection...")
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
                    _LOGGER.info(f"EcoFlow MQTT final status: Connected={connected}")
                    if not connected:
                        _LOGGER.warning("EcoFlow MQTT not yet connected - messages may arrive delayed")
                    else:
                        _LOGGER.info("EcoFlow MQTT fully connected and ready")
                        # Nach erfolgreicher Verbindung: Enhanced App Simulation für initialen Datenfluss
                        await asyncio.sleep(2)  # Kurz warten für Stabilisierung
                        _LOGGER.info("Triggering initial enhanced app simulation...")
                        await self.send_enhanced_app_simulation()
            
            # Nachrichten-Zähler für Debugging
            self.message_count = 0
            self.last_message_time = None
            
            # Keep-Alive System Konfiguration (natürlich wie echte EcoFlow App)
            self.keep_alive_interval = 300   # Quota-Abfragen alle 5 Minuten (wie echte App)
            self.heartbeat_interval = 180    # Heartbeat alle 3 Minuten (natürlich)
            self.status_interval = 60        # Status-Updates alle 60 Sekunden
            self.last_keep_alive = 0
            self.last_heartbeat = 0
            self.last_status_update = 0
            
            # Hauptschleife starten
            self.running = True
            status_counter = 0
            keep_alive_counter = 0
            heartbeat_counter = 0
            
            while self.running:
                current_time = time.time()
                
                # Keep-Alive Quota-Anfragen (alle 5 Minuten wie ioBroker)
                if current_time - self.last_keep_alive >= self.keep_alive_interval:
                    keep_alive_counter += 1
                    await self.send_keep_alive_messages()
                    self.last_keep_alive = current_time
                    
                    msg_info = f"Messages so far: {getattr(self, 'message_count', 0)}"
                    if getattr(self, 'last_message_time', None):
                        seconds_ago = int(time.time() - self.last_message_time)
                        msg_info += f", last {seconds_ago}s ago"
                    else:
                        msg_info += ", none received yet"
                    
                    _LOGGER.info(f"Keep-Alive #{keep_alive_counter} sent to {len(self.device_sns)} devices - {msg_info}")
                
                # Heartbeat-Nachrichten (alle 20 Sekunden - aggressiv vor Server-Timeout)
                if current_time - self.last_heartbeat >= self.heartbeat_interval:
                    heartbeat_counter += 1
                    await self.send_heartbeat_messages()
                    self.last_heartbeat = current_time
                    _LOGGER.debug(f"Heartbeat #{heartbeat_counter} sent to {len(self.device_sns)} devices")
                
                # Natürliche Verbindungsüberwachung: Sanfte Checks bei längerer Inaktivität
                if getattr(self, 'last_message_time', None):
                    time_since_last_msg = current_time - self.last_message_time
                    if time_since_last_msg > 120:  # Erst nach 2 Minuten ohne Nachrichten (natürlich)
                        # Sanfte Verbindungsüberprüfung statt aggressiver Heartbeats
                        _LOGGER.info(f"Natural check: {time_since_last_msg:.1f}s since last message - checking connection health")
                        mqtt_client = self.get_ecoflow_mqtt_client()
                        if mqtt_client and not mqtt_client.is_connected():
                            _LOGGER.warning("Connection appears disconnected - gentle recovery")
                            await self.gentle_connection_recovery()
                
                # Natürliche Verbindungsüberwachung nur wenn nötig (alle 15 Minuten statt 2 Minuten)
                if heartbeat_counter > 50 and heartbeat_counter % 50 == 0:  # Alle ~15 Minuten bei 3min-Heartbeats
                    mqtt_client = self.get_ecoflow_mqtt_client()
                    if mqtt_client and not mqtt_client.is_connected():
                        _LOGGER.warning("Periodic check: MQTT disconnected - gentle recovery")
                        await self.gentle_connection_recovery()
                        heartbeat_counter = 0
                    elif mqtt_client:
                        _LOGGER.info("Periodic check: MQTT connection stable")
                
                # Status-Updates senden (alle 60s)
                if current_time - self.last_status_update >= self.status_interval:
                    status_counter += 1
                    
                    # Status-Update senden
                    message_stats = {
                        'total_messages': getattr(self, 'message_count', 0),
                        'last_message_time': getattr(self, 'last_message_time', None),
                        'seconds_since_last_message': time.time() - getattr(self, 'last_message_time', time.time()) if getattr(self, 'last_message_time', None) else None,
                        'keep_alive_count': keep_alive_counter
                    }
                    
                    status = {
                        'status': 'running',
                        'timestamp': time.time(),
                        'devices': self.device_sns,
                        'messages': message_stats,
                        'status_update_count': status_counter,
                        'keep_alive_enabled': True,
                        'keep_alive_interval': self.keep_alive_interval
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
                            'status': 'connected',
                            'keep_alive_active': True
                        }
                        topic = f"{self.mqtt_base_topic}/{device_sn}/status"
                        self.mqtt_client.publish(topic, json.dumps(device_status), retain=True)
                    
                    self.last_status_update = current_time
                    _LOGGER.info(f"Status update #{status_counter} sent for {len(self.device_sns)} devices")
                
                # Natürliche Überwachung: Nur bei sehr langer Inaktivität prüfen (wie ioBroker)
                if getattr(self, 'last_message_time', None):
                    time_since_last_msg = current_time - self.last_message_time
                    # Nur bei 10+ Minuten ohne Nachrichten und nur einmal alle 5 Minuten warnen
                    if time_since_last_msg > 600:  # 10 Minuten wie im ioBroker-Repo
                        # Prüfe ob schon kürzlich gewarnt (verhindert Spam)
                        last_warning = getattr(self, 'last_warning_time', 0)
                        if current_time - last_warning > 300:  # Nur alle 5 Minuten warnen
                            _LOGGER.warning(f"No messages from devices within {time_since_last_msg/60:.1f} minutes - connection may be unstable")
                            self.last_warning_time = current_time
                            
                            # Nur bei sehr langer Inaktivität (20+ Minuten) Recovery versuchen
                            if time_since_last_msg > 1200:  # 20 Minuten
                                mqtt_client = self.get_ecoflow_mqtt_client()
                                if mqtt_client and not mqtt_client.is_connected():
                                    _LOGGER.warning("MQTT actually disconnected after 20+ minutes - attempting recovery")
                                    await self.gentle_connection_recovery()
                
                # Natürliche Pause wie echte Apps - nicht aggressive Kontrolle
                await asyncio.sleep(60)  # 1 Minute zwischen Checks (entspannt wie ioBroker)
                
        except Exception as e:
            _LOGGER.error(f"Error during startup: {e}")
            raise

    def stop(self):
        """Stoppt den Publisher"""
        _LOGGER.info("EcoFlow MQTT Publisher stopping...")
        self.running = False
        
        # Message timeout timer stoppen
        if hasattr(self, 'message_timeout_timer') and self.message_timeout_timer:
            self.message_timeout_timer.cancel()
            _LOGGER.info("Message timeout timer stopped")
        
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
