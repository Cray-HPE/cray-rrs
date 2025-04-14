import threading
from src.lib.lib_configmap import ConfigMapHelper

namespace = "rack-resiliency"
dynamic_cm = "dynamic-sravani-test"
static_cm = "static-sravani-test"

class RMSStateManager:
    def __init__(self):
        self.lock = threading.Lock()
        self.monitor_running = False
        self.rms_state = ""
        self.dynamic_cm_data = {}

    def set_state(self, new_state):
        with self.lock:
            self.rms_state = new_state

    def get_state(self):
        with self.lock:
            return self.rms_state

    def set_dynamic_cm_data(self, data):
        with self.lock:
            self.dynamic_cm_data = data

    def get_dynamic_cm_data(self):
        with self.lock:
            if not self.dynamic_cm_data:
                self.dynamic_cm_data = ConfigMapHelper.get_configmap(
                    namespace, dynamic_cm
                )
            return self.dynamic_cm_data

    def is_monitoring(self):
        with self.lock:
            return self.monitor_running

    def start_monitoring(self):
        with self.lock:
            if self.monitor_running:
                return False
            self.monitor_running = True
            return True

    def stop_monitoring(self):
        with self.lock:
            self.monitor_running = False
