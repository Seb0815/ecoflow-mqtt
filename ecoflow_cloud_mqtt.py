#!/usr/bin/env python3
"""
EcoFlow Cloud MQTT Publisher (ohne Home Assistant)
Standalone Version zum Weiterleiten von EcoFlow Daten per MQTT
"""

import asyncio
import json
import logging
import os
import signal
import sys
import time
from typing import Any, Dict, Optional

import paho.mqtt.client as mqtt

# Import der EcoFlow Cloud API Komponenten
from custom_components.ecoflow_cloud.api.private_api import EcoflowPrivateApiClient
from custom_components.ecoflow_cloud.api.public_api import EcoflowPublicApiClient
from custom_components.ecoflow_cloud.device_data import DeviceData, DeviceOptions

# Logging konfigurieren
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
_LOGGER = logging.getLogger(__name__)


class EcoflowMqttPublisher:
    """Standalone EcoFlow MQTT Publisher ohne Home Assistant Abhängigkeiten"""

    def __init__(self):
        self.api_client = None
        self.mqtt_client = None
        self.running = False
        self.devices = {}

        # Konfiguration aus Umgebungsvariablen laden
        self.load_config()

    def load_config(self):
        """Lädt Konfiguration aus Umgebungsvariablen"""
        # EcoFlow API Konfiguration
        self.auth_type = os.getenv("ECOFLOW_AUTH_TYPE", "private")  # private oder public
        
        # Private API (Email/Password)
        self.username = os.getenv("ECOFLOW_USERNAME")
        self.password = os.getenv("ECOFLOW_PASSWORD")
        
        # Public API (Access/Secret Key)
        self.access_key = os.getenv("ECOFLOW_ACCESS_KEY")
        self.secret_key = os.getenv("ECOFLOW_SECRET_KEY")
        
        # API Host
        self.api_host = os.getenv("ECOFLOW_API_HOST", "api.ecoflow.com")
        self.group = os.getenv("ECOFLOW_GROUP", "default")
        
        # Device Liste (kommagetrennt: "SN1:DEVICE_TYPE1:NAME1,SN2:DEVICE_TYPE2:NAME2")
        self.device_list_str = os.getenv("ECOFLOW_DEVICES", "")
        
        # MQTT Konfiguration
        self.mqtt_host = os.getenv("MQTT_HOST", "localhost")
        self.mqtt_port = int(os.getenv("MQTT_PORT", "1883"))
        self.mqtt_username = os.getenv("MQTT_USERNAME")
        self.mqtt_password = os.getenv("MQTT_PASSWORD")
        self.mqtt_base_topic = os.getenv("MQTT_BASE_TOPIC", "ecoflow")
        
        # Abfrage-Intervall
        self.refresh_interval = int(os.getenv("REFRESH_INTERVAL", "30"))

        # Konfiguration validieren
        if self.auth_type == "private":
            if not self.username or not self.password:
                raise ValueError("ECOFLOW_USERNAME und ECOFLOW_PASSWORD müssen für private API gesetzt sein")
        elif self.auth_type == "public":
            if not self.access_key or not self.secret_key:
                raise ValueError("ECOFLOW_ACCESS_KEY und ECOFLOW_SECRET_KEY müssen für public API gesetzt sein")
        else:
            raise ValueError("ECOFLOW_AUTH_TYPE muss 'private' oder 'public' sein")

    def parse_device_list(self) -> Dict[str, DeviceData]:
        """Parst die Device-Liste aus der Umgebungsvariable"""
        devices = {}
        
        if not self.device_list_str:
            _LOGGER.warning("Keine Geräte in ECOFLOW_DEVICES definiert")
            return devices
            
        for device_str in self.device_list_str.split(","):
            parts = device_str.strip().split(":")
            if len(parts) >= 3:
                sn, device_type, name = parts[0], parts[1], parts[2]
                options = DeviceOptions(
                    refresh_period_sec=self.refresh_interval,
                    power_step=50,
                    diagnostic_mode=False
                )
                devices[sn] = DeviceData(sn, name, device_type, options, None, None)
            else:
                _LOGGER.warning(f"Ungültiges Device-Format: {device_str}")
                
        return devices

    async def setup_api_client(self):
        """Erstellt und konfiguriert den EcoFlow API Client"""
        devices_list = self.parse_device_list()
        
        if self.auth_type == "private":
            self.api_client = EcoflowPrivateApiClient(
                self.api_host,
                self.username,
                self.password,
                self.group
            )
        else:  # public
            self.api_client = EcoflowPublicApiClient(
                self.api_host,
                self.access_key,
                self.secret_key,
                self.group
            )

        # Login durchführen
        await self.api_client.login()
        _LOGGER.info("Erfolgreich bei EcoFlow API angemeldet")

        # Geräte konfigurieren
        for sn, device_data in devices_list.items():
            device = self.api_client.configure_device(device_data)
            self.devices[sn] = device
            _LOGGER.info(f"Gerät konfiguriert: {device_data.name} ({sn})")

        # MQTT Client starten
        await asyncio.get_event_loop().run_in_executor(None, self.api_client.start)
        _LOGGER.info("EcoFlow MQTT Client gestartet")

    def setup_mqtt_client(self):
        """Konfiguriert den lokalen MQTT Client für die Weiterleitung"""
        self.mqtt_client = mqtt.Client()
        
        if self.mqtt_username and self.mqtt_password:
            self.mqtt_client.username_pw_set(self.mqtt_username, self.mqtt_password)
            
        self.mqtt_client.on_connect = self.on_mqtt_connect
        self.mqtt_client.on_disconnect = self.on_mqtt_disconnect
        
        try:
            self.mqtt_client.connect(self.mqtt_host, self.mqtt_port, 60)
            self.mqtt_client.loop_start()
            _LOGGER.info(f"Verbunden mit lokalem MQTT Broker: {self.mqtt_host}:{self.mqtt_port}")
        except Exception as e:
            _LOGGER.error(f"Fehler beim Verbinden mit MQTT Broker: {e}")
            raise

    def on_mqtt_connect(self, client, userdata, flags, rc):
        """Callback für MQTT Verbindung"""
        if rc == 0:
            _LOGGER.info("Erfolgreich mit lokalem MQTT Broker verbunden")
        else:
            _LOGGER.error(f"MQTT Verbindung fehlgeschlagen mit Code: {rc}")

    def on_mqtt_disconnect(self, client, userdata, rc):
        """Callback für MQTT Trennung"""
        _LOGGER.warning(f"MQTT Verbindung getrennt mit Code: {rc}")

    def publish_device_data(self, device):
        """Veröffentlicht Gerätedaten über MQTT"""
        if not self.mqtt_client:
            return
            
        try:
            # Alle Parameter des Geräts durchgehen
            for param_name, param_value in device.data.params.items():
                topic = f"{self.mqtt_base_topic}/{device.device_info.sn}/{param_name}"
                
                # Wert serialisieren
                if isinstance(param_value, (dict, list)):
                    payload = json.dumps(param_value)
                else:
                    payload = str(param_value)
                
                # Veröffentlichen
                self.mqtt_client.publish(topic, payload, retain=True)
                
            # Status-Informationen veröffentlichen
            status_topic = f"{self.mqtt_base_topic}/{device.device_info.sn}/status"
            status_data = {
                "device_name": device.device_info.name,
                "device_type": device.device_info.device_type,
                "sn": device.device_info.sn,
                "online": device.device_info.status == 1,
                "last_update": int(time.time())
            }
            self.mqtt_client.publish(status_topic, json.dumps(status_data), retain=True)
            
            _LOGGER.debug(f"Daten für Gerät {device.device_info.name} veröffentlicht")
            
        except Exception as e:
            _LOGGER.error(f"Fehler beim Veröffentlichen der Daten für {device.device_info.name}: {e}")

    async def data_loop(self):
        """Hauptschleife für die Datenabfrage und -veröffentlichung"""
        while self.running:
            try:
                # Quota-Anfrage für alle Geräte
                await self.api_client.quota_all(None)
                
                # Daten aller Geräte veröffentlichen
                for device in self.devices.values():
                    self.publish_device_data(device)
                
                _LOGGER.info(f"Daten für {len(self.devices)} Geräte aktualisiert")
                
            except Exception as e:
                _LOGGER.error(f"Fehler in der Datenabfrage-Schleife: {e}")
            
            # Warten bis zum nächsten Zyklus
            await asyncio.sleep(self.refresh_interval)

    async def start(self):
        """Startet den EcoFlow MQTT Publisher"""
        _LOGGER.info("EcoFlow MQTT Publisher startet...")
        
        try:
            # MQTT Client setup
            self.setup_mqtt_client()
            
            # EcoFlow API Client setup
            await self.setup_api_client()
            
            # Hauptschleife starten
            self.running = True
            await self.data_loop()
            
        except Exception as e:
            _LOGGER.error(f"Fehler beim Start: {e}")
            raise

    def stop(self):
        """Stoppt den Publisher"""
        _LOGGER.info("EcoFlow MQTT Publisher wird gestoppt...")
        self.running = False
        
        if self.api_client:
            self.api_client.stop()
            
        if self.mqtt_client:
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()


def signal_handler(signum, frame):
    """Signal Handler für graceful shutdown"""
    _LOGGER.info(f"Signal {signum} empfangen, beende...")
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
    except KeyboardInterrupt:
        _LOGGER.info("Beenden durch Benutzer...")
    except Exception as e:
        _LOGGER.error(f"Unerwarteter Fehler: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
