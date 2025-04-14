import logging
import threading
from typing import Dict, Any
from src.lib.lib_configmap import ConfigMapHelper

logger = logging.getLogger()


class RMSStateManager:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.monitor_running = False
        self.rms_state = ""
        self.dynamic_cm_data = {}
        self.namespace = "rack-resiliency"
        self.dynamic_cm = "dynamic-sravani-test"
        self.static_cm = "static-sravani-test"

    def set_state(self, new_state: str) -> None:
        with self.lock:
            self.rms_state = new_state

    def get_state(self) -> str:
        with self.lock:
            return self.rms_state

    def set_dynamic_cm_data(self, data) -> None:
        with self.lock:
            self.dynamic_cm_data = data

    def get_dynamic_cm_data(self) -> Dict[str, str] | Any:
        with self.lock:
            if not self.dynamic_cm_data:
                self.dynamic_cm_data = ConfigMapHelper.get_configmap(
                    self.namespace, self.dynamic_cm
                )
            return self.dynamic_cm_data

    def is_monitoring(self) -> bool:
        with self.lock:
            return self.monitor_running

    def start_monitoring(self) -> bool:
        with self.lock:
            if self.monitor_running:
                return False
            self.monitor_running = True
            return True

    def stop_monitoring(self) -> None:
        with self.lock:
            self.monitor_running = False
