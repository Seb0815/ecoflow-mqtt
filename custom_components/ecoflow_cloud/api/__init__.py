import logging
from abc import ABC, abstractmethod
from typing import Any, Optional, Union, Dict
from dataclasses import dataclass

import aiohttp
from aiohttp import ClientResponse

from ..device_data import DeviceData
from .message import JSONMessage, Message

_LOGGER = logging.getLogger(__name__)


class EcoflowException(Exception):
    pass


@dataclass
class EcoflowMqttInfo:
    url: str
    port: int
    username: str
    password: str
    client_id: Optional[str] = None


class EcoflowApiClient(ABC):
    def __init__(self):
        self.mqtt_info: EcoflowMqttInfo = None
        self.devices: Dict[str, Any] = {}
        self.mqtt_client = None

    @abstractmethod
    async def login(self):
        pass

    @abstractmethod
    async def fetch_all_available_devices(self):
        pass

    @abstractmethod
    async def quota_all(self, device_sn: Optional[str]):
        pass

    @abstractmethod
    def configure_device(self, device_data: DeviceData):
        pass

    def add_device(self, device):
        self.devices[device.device_data.sn] = device

    def _accept_mqqt_certification(self, response):
        cert_data = response["data"]
        self.mqtt_info = EcoflowMqttInfo(
            url=cert_data["url"],
            port=int(cert_data["port"]),
            username=cert_data["certificateAccount"],
            password=cert_data["certificatePassword"],
        )

    async def _get_json_response(self, response: aiohttp.ClientResponse) -> dict:
        if response.status == 200:
            json_response = await response.json()
            if json_response["code"] == "0":
                return json_response
            else:
                raise EcoflowException(
                    f"Got error response {json_response['code']}: {json_response['message']}"
                )
        else:
            raise EcoflowException(
                f"Invalid response status code {response.status}: {await response.text()}"
            )

    def start(self):
        """Startet den MQTT Client"""
        if self.mqtt_info:
            # Hier würde der MQTT Client initialisiert werden
            # Für standalone Version ist das optional
            _LOGGER.info("MQTT Client würde hier gestartet werden")
        else:
            _LOGGER.warning("Keine MQTT Info verfügbar")

    def stop(self):
        """Stoppt den MQTT Client"""
        if hasattr(self, 'mqtt_client') and self.mqtt_client:
            self.mqtt_client.disconnect()

    def send_get_message(self, device_sn: str, command: Union[Dict, Message]):
        """Sendet eine GET-Nachricht an ein Gerät"""
        if hasattr(self, 'mqtt_client') and self.mqtt_client:
            # MQTT Implementierung hier
            pass
        else:
            _LOGGER.debug(f"Würde GET-Nachricht senden: {device_sn}, {command}")

    def send_set_message(
        self, device_sn: str, mqtt_state: Dict[str, Any], command: Union[Dict, Message]
    ):
        """Sendet eine SET-Nachricht an ein Gerät"""
        if hasattr(self, 'mqtt_client') and self.mqtt_client:
            # MQTT Implementierung hier
            pass
        else:
            _LOGGER.debug(f"Würde SET-Nachricht senden: {device_sn}, {mqtt_state}, {command}")

    def is_connected(self) -> bool:
        """Prüft ob der MQTT Client verbunden ist"""
        if hasattr(self, 'mqtt_client') and self.mqtt_client:
            return getattr(self.mqtt_client, 'is_connected', lambda: False)()
        return False

    def remove_device(self, device):
        self.devices.pop(device.device_data.sn, None)

    def _accept_mqqt_certification(self, resp_json: dict):
        _LOGGER.info(f"Received MQTT credentials: {resp_json}")
        try:
            mqtt_url = resp_json["data"]["url"]
            mqtt_port = int(resp_json["data"]["port"])
            mqtt_username = resp_json["data"]["certificateAccount"]
            mqtt_password = resp_json["data"]["certificatePassword"]
            self.mqtt_info = EcoflowMqttInfo(
                mqtt_url, mqtt_port, mqtt_username, mqtt_password
            )
        except KeyError as key:
            raise EcoflowException(f"Failed to extract key {key} from {resp_json}")

        _LOGGER.info(f"Successfully extracted account: {self.mqtt_info.username}")

    async def _get_json_response(self, resp: ClientResponse):
        if resp.status != 200:
            raise EcoflowException(f"Got HTTP status code {resp.status}: {resp.reason}")

        try:
            json_resp = await resp.json()
            response_message = json_resp["message"]
        except KeyError as key:
            raise EcoflowException(f"Failed to extract key {key} from {resp}")
        except Exception as error:
            raise EcoflowException(
                f"Failed to parse response: {resp.text} Error: {error}"
            )

        if response_message.lower() != "success":
            raise EcoflowException(f"{response_message}")

        return json_resp

    def send_get_message(self, device_sn: str, command: Union[Dict, Message]):
        if isinstance(command, dict):
            command = JSONMessage(command)

        self.mqtt_client.publish(
            self.devices[device_sn].device_info.get_topic, command.to_mqtt_payload()
        )

    def send_set_message(
        self, device_sn: str, mqtt_state: Dict[str, Any], command: Union[Dict, Message]
    ):
        if isinstance(command, dict):
            command = JSONMessage(command)

        self.devices[device_sn].data.update_to_target_state(mqtt_state)
        self.mqtt_client.publish(
            self.devices[device_sn].device_info.set_topic, command.to_mqtt_payload()
        )

    def start(self):
        from custom_components.ecoflow_cloud.api.ecoflow_mqtt import EcoflowMQTTClient

        # Extrahiere Seriennummern falls devices leer ist aber device_sns verfügbar
        device_sns = list(self.devices.keys()) if self.devices else getattr(self, 'device_sns', [])
        self.mqtt_client = EcoflowMQTTClient(self.mqtt_info, self.devices, device_sns)

    def stop(self):
        assert self.mqtt_client is not None
        self.mqtt_client.stop()
