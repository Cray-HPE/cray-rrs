#
# MIT License
#
#  (C) Copyright 2025 Hewlett Packard Enterprise Development LP
#
# Permission is hereby granted, free of charge, to any person obtaining a
# copy of this software and associated documentation files (the "Software"),
# to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense,
# and/or sell copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included
# in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR
# OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
# ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.
#

"""
RMS State Manager Module

This module defines the RMSStateManager class, which handles the synchronization and
management of state transitions for the Rack Resiliency Service (RRS) monitoring logic.
"""

import threading
from typing import Dict, Any
from src.lib.lib_configmap import ConfigMapHelper
from src.lib.rrs_constants import *


class RMSStateManager:
    """
    RMSStateManager handles the monitoring state and access to dynamic ConfigMap data
    for the Rack Resiliency Service (RRS).
    """

    def __init__(self) -> None:
        """Initialize the state manager with default state values and resource identifiers."""
        self.lock = threading.Lock()
        self.monitor_running = False
        self.rms_state = ""
        self.dynamic_cm_data: Dict[str, Any] = {}

    def set_state(self, new_state: str) -> None:
        """Thread-safe method to set the current RMS state."""
        with self.lock:
            self.rms_state = new_state

    def get_state(self) -> str:
        """Thread-safe method to retrieve the current RMS state."""
        with self.lock:
            return self.rms_state

    def set_dynamic_cm_data(self, data: Dict[str, Any]) -> None:
        """Thread-safe method to update the dynamic ConfigMap data."""
        with self.lock:
            self.dynamic_cm_data = data

    def get_dynamic_cm_data(self) -> Dict[str, str] | Any:
        """Thread-safe method to retrieve the dynamic ConfigMap data."""
        with self.lock:
            if not self.dynamic_cm_data:
                self.dynamic_cm_data = ConfigMapHelper.read_configmap(
                    NAMESPACE, DYNAMIC_CM
                )
            return self.dynamic_cm_data

    def is_monitoring(self) -> bool:
        """Thread-safe check to determine if monitoring is currently active."""
        with self.lock:
            return self.monitor_running

    def start_monitoring(self) -> bool:
        """Thread-safe method to initiate monitoring."""
        with self.lock:
            if self.monitor_running:
                return False
            self.monitor_running = True
            return True

    def stop_monitoring(self) -> None:
        """Thread-safe method to stop the monitoring process."""
        with self.lock:
            self.monitor_running = False
