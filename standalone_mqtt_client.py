import logging
import ssl
import time
from typing import Any, Dict
import paho.mqtt.client as mqtt

_LOGGER = logging.getLogger(__name__)


class EcoflowMQTTClient:
    """Standalone EcoFlow MQTT Client ohne Home Assistant Abhängigkeiten"""
    
    def __init__(self, mqtt_info, devices: Dict[str, Any]):
        self.connected = False
        self.__mqtt_info = mqtt_info
        self.__devices = devices
        
        # Standard MQTT Client verwenden statt Home Assistant spezifischen
        self.__client = mqtt.Client(
            client_id=self.__mqtt_info.client_id,
            clean_session=True
        )
        
        # SSL/TLS Konfiguration
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_REQUIRED
        
        self.__client.tls_set_context(context)
        self.__client.username_pw_set(
            self.__mqtt_info.username, 
            self.__mqtt_info.password
        )
        
        # Callbacks setzen
        self.__client.on_connect = self._on_connect
        self.__client.on_disconnect = self._on_disconnect
        self.__client.on_message = self._on_message
        
        _LOGGER.info(
            f"Connecting to MQTT Broker {self.__mqtt_info.url}:{self.__mqtt_info.port} "
            f"with client id {self.__mqtt_info.client_id} and username {self.__mqtt_info.username}"
        )

    def connect(self):
        """Verbindet mit dem MQTT Broker"""
        try:
            self.__client.connect(self.__mqtt_info.url, self.__mqtt_info.port, keepalive=15)
            self.__client.loop_start()
        except Exception as e:
            _LOGGER.error(f"Fehler beim Verbinden mit MQTT Broker: {e}")
            raise

    def disconnect(self):
        """Trennt die Verbindung zum MQTT Broker"""
        self.__client.loop_stop()
        self.__client.disconnect()

    def is_connected(self):
        """Prüft ob die Verbindung aktiv ist"""
        return self.connected

    def _on_connect(self, client, userdata, flags, rc):
        """Callback für MQTT Verbindung"""
        if rc == 0:
            self.connected = True
            _LOGGER.info("Erfolgreich mit EcoFlow MQTT Broker verbunden")
            
            # Alle relevanten Topics abonnieren
            for sn in self.__devices.keys():
                topics = [
                    f"/app/device/property/{sn}",
                    f"/app/{sn}/thing/property/set",
                    f"/app/{sn}/thing/property/get_reply",
                    f"/app/{sn}/thing/property/set_reply"
                ]
                
                for topic in topics:
                    client.subscribe(topic, qos=1)
                    _LOGGER.debug(f"Subscribed to topic: {topic}")
        else:
            _LOGGER.error(f"MQTT Verbindung fehlgeschlagen mit Code: {rc}")

    def _on_disconnect(self, client, userdata, rc):
        """Callback für MQTT Trennung"""
        self.connected = False
        if rc != 0:
            _LOGGER.warning(f"Unerwartete MQTT Trennung mit Code: {rc}")
        else:
            _LOGGER.info("MQTT Verbindung getrennt")

    def _on_message(self, client, userdata, message):
        """Callback für eingehende MQTT Nachrichten"""
        try:
            topic = message.topic
            payload = message.payload.decode('utf-8')
            
            _LOGGER.debug(f"Received message on topic {topic}: {payload}")
            
            # Device SN aus Topic extrahieren
            topic_parts = topic.split('/')
            if len(topic_parts) >= 4:
                sn = topic_parts[3]
                
                if sn in self.__devices:
                    device = self.__devices[sn]
                    
                    # Message an das entsprechende Device weiterleiten
                    if hasattr(device, 'process_message'):
                        device.process_message(topic, payload)
                    
        except Exception as e:
            _LOGGER.error(f"Fehler beim Verarbeiten der MQTT Nachricht: {e}")

    def send_message(self, sn: str, message_type: str, data: Dict[str, Any]):
        """Sendet eine Nachricht an ein spezifisches Gerät"""
        if not self.connected:
            _LOGGER.warning("MQTT Client nicht verbunden")
            return False
            
        try:
            import json
            
            topic = f"/app/{sn}/thing/property/{message_type}"
            payload = json.dumps(data)
            
            result = self.__client.publish(topic, payload, qos=1)
            
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                _LOGGER.debug(f"Nachricht gesendet an {topic}: {payload}")
                return True
            else:
                _LOGGER.error(f"Fehler beim Senden der Nachricht: {result.rc}")
                return False
                
        except Exception as e:
            _LOGGER.error(f"Fehler beim Senden der MQTT Nachricht: {e}")
            return False

    def quota(self, sn: str):
        """Fordert Quota-Daten für ein Gerät an"""
        quota_data = {
            "from": "HomeAssistant",
            "id": str(int(time.time() * 1000)),
            "version": "1.0"
        }
        return self.send_message(sn, "get", quota_data)
