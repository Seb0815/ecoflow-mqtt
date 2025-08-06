import logging
import ssl
import time
from _socket import SocketType
from typing import Any

# Dummy callback decorator for standalone operation
def callback(func):
    return func

from paho.mqtt.client import MQTTMessage, PayloadType

from ..devices import BaseDevice
from . import EcoflowMqttInfo

_LOGGER = logging.getLogger(__name__)


class EcoflowMQTTClient:
    def __init__(self, mqtt_info: EcoflowMqttInfo, devices: dict[str, BaseDevice], device_sns: list = None):
        from ..devices import BaseDevice
        import paho.mqtt.client as mqtt

        self.connected = False
        self.__mqtt_info = mqtt_info
        self.__devices: dict[str, BaseDevice] = devices
        self.__device_sns = device_sns or list(devices.keys())

        # Use standard paho-mqtt client instead of HA's AsyncMQTTClient
        self.__client = mqtt.Client(
            client_id=self.__mqtt_info.client_id,
            clean_session=True,
        )

        self.__client.username_pw_set(
            self.__mqtt_info.username, self.__mqtt_info.password
        )
        self.__client.tls_set(certfile=None, keyfile=None, cert_reqs=ssl.CERT_REQUIRED)
        self.__client.tls_insecure_set(False)
        self.__client.on_connect = self._on_connect
        self.__client.on_disconnect = self._on_disconnect
        self.__client.on_message = self._on_message
        self.__client.on_socket_close = self._on_socket_close

        _LOGGER.info(
            f"Connecting to MQTT Broker {self.__mqtt_info.url}:{self.__mqtt_info.port} with client id {self.__mqtt_info.client_id} and username {self.__mqtt_info.username}"
        )
        self.__client.connect(self.__mqtt_info.url, self.__mqtt_info.port, keepalive=15)
        self.__client.loop_start()

    def is_connected(self):
        return self.__client.is_connected()

    def start(self):
        """Start the MQTT client"""
        self.__client.loop_start()

    def reconnect(self) -> bool:
        try:
            _LOGGER.info(
                f"Re-connecting to MQTT Broker {self.__mqtt_info.url}:{self.__mqtt_info.port}"
            )
            self.__client.loop_stop(True)
            self.__client.reconnect()
            self.__client.loop_start()
            return True
        except Exception as e:
            _LOGGER.error(e)
            return False

    @callback
    def _on_socket_close(self, client, userdata: Any, sock: SocketType) -> None:
        _LOGGER.error(f"Unexpected MQTT Socket disconnection : {str(sock)}")

    @callback
    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self.connected = True
            target_topics = [(topic, 1) for topic in self.__target_topics()]
            
            # Prüfe ob Topics vorhanden sind
            if target_topics:
                self.__client.subscribe(target_topics)
                _LOGGER.info(f"Subscribed to MQTT topics {target_topics}")
            else:
                # Fallback: Subscribe zu allen Device-Topics direkt basierend auf Seriennummern
                device_topics = []
                for device_sn in self.__device_sns:
                    # Standard EcoFlow Topic Patterns - erweitert für bessere Abdeckung
                    patterns = [
                        f"/app/device/property/{device_sn}",
                        f"/app/{device_sn}/+",
                        f"/app/+/{device_sn}/+",
                        f"/app/device/quota/{device_sn}",
                        f"/{device_sn}/+",
                        f"+/{device_sn}/+/+",
                        f"/topic/device/{device_sn}/+/+",
                        f"/topic/{device_sn}/+/+"
                    ]
                    device_topics.extend([(topic, 1) for topic in patterns])
                
                if device_topics:
                    self.__client.subscribe(device_topics)
                    _LOGGER.info(f"Subscribed to {len(device_topics)} fallback device topics for {len(self.__device_sns)} devices")
                    _LOGGER.debug(f"Topics: {[topic[0] for topic in device_topics[:10]]}...")  # Zeige nur erste 10
                else:
                    _LOGGER.warning("Keine Topics zum Abonnieren gefunden")
        else:
            self.__log_with_reason("connect", client, userdata, rc)

    @callback
    def _on_disconnect(self, client, userdata, rc):
        if not self.connected:
            # from homeassistant/components/mqtt/client.py
            # This function is re-entrant and may be called multiple times
            # when there is a broken pipe error.
            return
        self.connected = False
        if rc != 0:
            self.__log_with_reason("disconnect", client, userdata, rc)
            time.sleep(5)

    @callback
    def _on_message(self, client, userdata, message: MQTTMessage):
        try:
            for sn, device in self.__devices.items():
                if device.update_data(message.payload, message.topic):
                    _LOGGER.debug(
                        f"Message for {sn} and Topic {message.topic} : {message.payload}"
                    )
        except UnicodeDecodeError as error:
            _LOGGER.error(
                f"UnicodeDecodeError: {error}. Ignoring message and waiting for the next one."
            )

    def stop(self):
        self.__client.unsubscribe(self.__target_topics())
        self.__client.loop_stop()
        self.__client.disconnect()

    def __log_with_reason(self, action: str, client, userdata, rc):
        import paho.mqtt.client as mqtt_client

        _LOGGER.error(
            f"MQTT {action}: {mqtt_client.error_string(rc)} ({self.__mqtt_info.client_id}) - {userdata}"
        )

    def publish(self, topic: str, message: PayloadType) -> None:
        try:
            info = self.__client.publish(topic, message, 1)
            _LOGGER.debug(
                "Sending "
                + str(message)
                + " :"
                + str(info)
                + "("
                + str(info.is_published())
                + ")"
            )
        except RuntimeError as error:
            _LOGGER.error(
                error, "Error on topic " + topic + " and message " + str(message)
            )
        except Exception as error:
            _LOGGER.debug(
                error, "Error on topic " + topic + " and message " + str(message)
            )

    def __target_topics(self) -> list[str]:
        topics = []
        
        # 🔥 WICHTIG: Account-basierte Topics wie die offizielle App!
        certificate_topics = []
        # Korrigierter Name: EcoflowMQTTClient (nicht EcoflowMqttClient)
        if hasattr(self, '_EcoflowMQTTClient__mqtt_info') and self.__mqtt_info:
            certificate_account = self.__mqtt_info.username
            # Das sind die Topics, die die offizielle App verwendet:
            certificate_topics = [
                f"/app/{certificate_account}/+",  # 🎯 DAS ist der Hauptkanal!
                f"/app/device/property/+",        # Device properties 
                f"/app/device/quota/+",           # Device quota updates
            ]
            topics.extend(certificate_topics)
            _LOGGER.info(f"Adding certificate-based topics for account: {certificate_account}")
            _LOGGER.info(f"Certificate topics added: {certificate_topics}")
        else:
            _LOGGER.warning(f"No MQTT info available for certificate-based topics. hasattr result: {hasattr(self, '_EcoflowMQTTClient__mqtt_info')}, mqtt_info: {getattr(self, '__mqtt_info', 'NOT_FOUND')}")
        
        # Device-specific topics als ZUSÄTZLICHE Backup-Topics
        device_topics_added = False
        for device in self.__devices.values():
            try:
                if hasattr(device, 'device_info') and hasattr(device.device_info, 'topics'):
                    for topic in device.device_info.topics():
                        topics.append(topic)
                        device_topics_added = True
                elif hasattr(device, 'device_data'):
                    device_sn = device.device_data.sn
                    additional_topics = [
                        f"/app/device/property/{device_sn}",
                        f"/app/device/quota/{device_sn}",
                    ]
                    topics.extend(additional_topics)
                    device_topics_added = True
                    _LOGGER.debug(f"Added device-specific topics: {additional_topics}")
            except Exception as e:
                _LOGGER.debug(f"Fehler beim Ermitteln der Topics für Device: {e}")
        
        # Fallback NUR wenn keine Device-Topics gefunden wurden
        if not device_topics_added and self.__device_sns:
            for device_sn in self.__device_sns:
                fallback_topics = [
                    f"/app/device/property/{device_sn}",
                    f"/app/device/quota/{device_sn}",
                ]
                topics.extend(fallback_topics)
                _LOGGER.debug(f"Added fallback topics: {fallback_topics}")
        
        # Remove duplicates that can occur when multiple devices have the same topic
        unique_topics = list(set(topics)) if topics else []
        
        # 🔥 VERIFY: Stelle sicher, dass certificate-based Topics dabei sind!
        if certificate_topics:
            for cert_topic in certificate_topics:
                if cert_topic not in unique_topics:
                    _LOGGER.error(f"CRITICAL: Certificate topic missing from final list: {cert_topic}")
                    unique_topics.append(cert_topic)  # Force add
                else:
                    _LOGGER.info(f"✅ Certificate topic confirmed in final list: {cert_topic}")
        
        _LOGGER.info(f"Final subscription topics: {unique_topics}")
        return unique_topics
