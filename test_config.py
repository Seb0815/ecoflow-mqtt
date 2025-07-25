#!/usr/bin/env python3
"""
Test-Script für EcoFlow Cloud MQTT Publisher
Prüft die Konfiguration und Verbindung ohne vollständigen Start
"""

import asyncio
import logging
import os
import sys

# Logging konfigurieren
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
_LOGGER = logging.getLogger(__name__)


def test_config():
    """Testet die Konfiguration"""
    _LOGGER.info("🔍 Teste Konfiguration...")
    
    # Erforderliche Umgebungsvariablen prüfen
    auth_type = os.getenv("ECOFLOW_AUTH_TYPE", "private")
    
    if auth_type == "private":
        username = os.getenv("ECOFLOW_USERNAME")
        password = os.getenv("ECOFLOW_PASSWORD")
        
        if not username or not password:
            _LOGGER.error("❌ ECOFLOW_USERNAME und ECOFLOW_PASSWORD müssen gesetzt sein")
            return False
        _LOGGER.info("✅ Private API Credentials gefunden")
        
    elif auth_type == "public":
        access_key = os.getenv("ECOFLOW_ACCESS_KEY")
        secret_key = os.getenv("ECOFLOW_SECRET_KEY")
        
        if not access_key or not secret_key:
            _LOGGER.error("❌ ECOFLOW_ACCESS_KEY und ECOFLOW_SECRET_KEY müssen gesetzt sein")
            return False
        _LOGGER.info("✅ Public API Credentials gefunden")
    else:
        _LOGGER.error("❌ ECOFLOW_AUTH_TYPE muss 'private' oder 'public' sein")
        return False
    
    # Device-Liste prüfen
    devices_str = os.getenv("ECOFLOW_DEVICES", "")
    if not devices_str:
        _LOGGER.warning("⚠️  Keine Geräte in ECOFLOW_DEVICES definiert")
        return False
    
    # Device-Format validieren
    devices = []
    for device_str in devices_str.split(","):
        parts = device_str.strip().split(":")
        if len(parts) >= 3:
            sn, device_type, name = parts[0], parts[1], parts[2]
            devices.append((sn, device_type, name))
            _LOGGER.info(f"✅ Gerät: {name} ({device_type}) - SN: {sn}")
        else:
            _LOGGER.warning(f"⚠️  Ungültiges Device-Format: {device_str}")
    
    if not devices:
        _LOGGER.error("❌ Keine gültigen Geräte gefunden")
        return False
    
    # MQTT Konfiguration prüfen
    mqtt_host = os.getenv("MQTT_HOST", "localhost")
    mqtt_port = int(os.getenv("MQTT_PORT", "1883"))
    _LOGGER.info(f"✅ MQTT Broker: {mqtt_host}:{mqtt_port}")
    
    _LOGGER.info("✅ Konfiguration ist gültig!")
    return True


async def test_api_connection():
    """Testet die Verbindung zur EcoFlow API"""
    _LOGGER.info("🌐 Teste EcoFlow API Verbindung...")
    
    try:
        # Import der EcoFlow API Komponenten
        from custom_components.ecoflow_cloud.api.private_api import EcoflowPrivateApiClient
        from custom_components.ecoflow_cloud.api.public_api import EcoflowPublicApiClient
        
        auth_type = os.getenv("ECOFLOW_AUTH_TYPE", "private")
        api_host = os.getenv("ECOFLOW_API_HOST", "api.ecoflow.com")
        group = os.getenv("ECOFLOW_GROUP", "default")
        
        if auth_type == "private":
            username = os.getenv("ECOFLOW_USERNAME")
            password = os.getenv("ECOFLOW_PASSWORD")
            api_client = EcoflowPrivateApiClient(api_host, username, password, group)
        else:
            access_key = os.getenv("ECOFLOW_ACCESS_KEY")
            secret_key = os.getenv("ECOFLOW_SECRET_KEY")
            api_client = EcoflowPublicApiClient(api_host, access_key, secret_key, group)
        
        # Login testen
        await api_client.login()
        _LOGGER.info("✅ EcoFlow API Login erfolgreich!")
        
        # Verfügbare Geräte abfragen
        devices = await api_client.fetch_all_available_devices()
        _LOGGER.info(f"✅ {len(devices)} Geräte in der Cloud gefunden:")
        
        for device in devices:
            status = "🟢 Online" if device.status == 1 else "🔴 Offline"
            _LOGGER.info(f"   - {device.name} ({device.device_type}) - SN: {device.sn} - {status}")
        
        return True
        
    except Exception as e:
        _LOGGER.error(f"❌ API Verbindung fehlgeschlagen: {e}")
        return False


def test_mqtt_connection():
    """Testet die MQTT Verbindung"""
    _LOGGER.info("📡 Teste MQTT Verbindung...")
    
    try:
        import paho.mqtt.client as mqtt
        
        mqtt_host = os.getenv("MQTT_HOST", "localhost")
        mqtt_port = int(os.getenv("MQTT_PORT", "1883"))
        mqtt_username = os.getenv("MQTT_USERNAME")
        mqtt_password = os.getenv("MQTT_PASSWORD")
        
        client = mqtt.Client()
        
        if mqtt_username and mqtt_password:
            client.username_pw_set(mqtt_username, mqtt_password)
        
        # Verbindung testen
        client.connect(mqtt_host, mqtt_port, 10)
        client.disconnect()
        
        _LOGGER.info("✅ MQTT Verbindung erfolgreich!")
        return True
        
    except Exception as e:
        _LOGGER.error(f"❌ MQTT Verbindung fehlgeschlagen: {e}")
        return False


async def main():
    """Hauptfunktion für den Test"""
    _LOGGER.info("🚀 Starte EcoFlow Cloud MQTT Publisher Test...")
    
    success = True
    
    # Konfiguration testen
    if not test_config():
        success = False
    
    # MQTT Verbindung testen
    if not test_mqtt_connection():
        success = False
    
    # API Verbindung testen
    if not await test_api_connection():
        success = False
    
    if success:
        _LOGGER.info("🎉 Alle Tests erfolgreich! Der Publisher sollte funktionieren.")
        sys.exit(0)
    else:
        _LOGGER.error("💥 Ein oder mehrere Tests fehlgeschlagen. Bitte Konfiguration prüfen.")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
