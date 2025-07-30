import logging
from collections.abc import Callable
from typing import Any, TypeVar, Optional, Dict, List, Union
from datetime import datetime

import jsonpath_ng.ext as jp

_LOGGER = logging.getLogger(__name__)

_T = TypeVar("_T")

# Standalone datetime utility functions
class dt:
    @staticmethod
    def utcnow():
        # Python 3.13 compatible: use timezone.utc instead of deprecated utcnow()
        try:
            from datetime import timezone
            return datetime.now(timezone.utc).replace(tzinfo=None)  # Keep old behavior
        except ImportError:
            # Fallback for older Python versions
            return datetime.utcnow()
    
    @staticmethod
    def now():
        return datetime.now()


class BoundFifoList(list):
    def __init__(self, maxlen=20) -> None:
        super().__init__()
        self.maxlen = maxlen

    def append(self, __object: _T) -> None:
        super().insert(0, __object)
        while len(self) >= self.maxlen:
            self.pop()


class EcoflowDataHolder:
    def __init__(
        self,
        extract_quota_message: Callable[[Dict[str, Any]], Dict[str, Any]],
        module_sn: Optional[str] = None,
        collect_raw: bool = False,
    ):
        self.__collect_raw = collect_raw
        self.extract_quota_message = extract_quota_message
        self.set = BoundFifoList()  # type: ignore
        self.set_reply = BoundFifoList()  # type: ignore
        self.set_reply_time = dt.utcnow().replace(
            year=2000, month=1, day=1, hour=0, minute=0, second=0
        )

        self.module_sn = module_sn

        self.get = BoundFifoList()  # type: ignore
        self.get_reply = BoundFifoList()  # type: ignore
        self.get_reply_time = dt.utcnow().replace(
            year=2000, month=1, day=1, hour=0, minute=0, second=0
        )

        self.params = {}  # type: Dict[str, Any]
        self.params_time = dt.utcnow().replace(
            year=2000, month=1, day=1, hour=0, minute=0, second=0
        )

        self.status = {}  # type: Dict[str, Any]
        self.status_time = dt.utcnow().replace(
            year=2000, month=1, day=1, hour=0, minute=0, second=0
        )

        self.raw_data = BoundFifoList()  # type: ignore

    def last_received_time(self):
        return max(
            self.status_time, self.params_time, self.get_reply_time, self.set_reply_time
        )

    def add_set_message(self, msg: Dict[str, Any]):
        self.set.append(msg)

    def add_set_reply_message(self, msg: Dict[str, Any]):
        self.set_reply.append(msg)
        self.set_reply_time = dt.utcnow()

    def add_get_message(self, msg: Dict[str, Any]):
        self.get.append(msg)

    def add_get_reply_message(self, msg: Dict[str, Any]):
        try:
            result = self.extract_quota_message(msg)
        except:
            result = None

        if result is not None:
            self.update_data(result)

        self.get_reply.append(msg)
        self.get_reply_time = dt.utcnow()

    def update_to_target_state(self, target_state: Dict[str, Any]):
        # key can be xpath!
        for key, value in target_state.items():
            jp.parse(key).update(self.params, value)

        self.params_time = dt.utcnow()

    def update_status(self, raw: Dict[str, Any]):
        self.status.update({"status": int(raw["params"]["status"])})
        self.status_time = dt.utcnow()

    def update_data(self, raw: Dict[str, Any]):
        if raw is not None:
            self.__add_raw_data(raw)
            try:
                if self.module_sn is not None:
                    if "moduleSn" not in raw:
                        return
                    if raw["moduleSn"] != self.module_sn:
                        return
                if "params" in raw:
                    self.params.update(raw["params"])
                    self.params_time = dt.utcnow()

            except Exception as error:
                _LOGGER.error("Error updating data: %s", error)

    def __add_raw_data(self, raw: Dict[str, Any]):
        if self.__collect_raw:
            self.raw_data.append(raw)
