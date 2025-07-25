import json
import random
import sys
from abc import ABC, abstractmethod
from typing import Union, Dict, List

# Python 3.12+ compatibility
if sys.version_info >= (3, 12):
    # Python 3.11 compatibility - override decorator nicht verfügbar
    def override(func):
        """Python 3.11 compatible override decorator"""
        return func
else:
    # Fallback for Python < 3.12
    def override(func):
        return func

from paho.mqtt.client import PayloadType


class Message(ABC):
    @abstractmethod
    def to_mqtt_payload(self) -> PayloadType:
        raise NotImplementedError()


JSONType = Union[None, bool, int, float, str, List["JSONType"], Dict[str, "JSONType"]]
JSONDict = Dict[str, JSONType]


class JSONMessage(Message):
    def __init__(self, data: JSONDict) -> None:
        super().__init__()
        self.data = data

    @staticmethod
    def gen_seq() -> int:
        return 999900000 + random.randint(10000, 99999)

    @staticmethod
    def prepare_payload(command: JSONDict) -> JSONDict:
        payload: JSONDict = {
            "from": "HomeAssistant",
            "id": str(JSONMessage.gen_seq()),
            "version": "1.0",
        }
        payload.update(command)
        return payload

    @override
    def to_mqtt_payload(self) -> PayloadType:
        return json.dumps(JSONMessage.prepare_payload(self.data))
