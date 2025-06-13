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
This module provides logging utilities to generate and manage log IDs,
convert log levels from strings to integers, and log events in a consistent format.
"""

import logging
import uuid
from flask import g
from flask import current_app as app


def get_log_id() -> str:
    """
    Generate a unique log ID that can be used to tie related log entries together.

    Returns:
        str: A unique 8-character string ID.
    """
    return str(uuid.uuid4())[:8]


def str_to_log_level(level: str) -> int:
    """
    Convert a string representation of a log level to its corresponding logging level constant.

    Args:
        level (str): The log level as a string, e.g., "INFO", "DEBUG", "ERROR".

    Returns:
        int: The corresponding logging level constant from the logging module.
    """
    name_to_level = logging.getLevelNamesMapping()
    return name_to_level.get(level.upper(), logging.INFO)


def log_event(message: str, level: str = "INFO") -> None:
    """
    Log an event with a dynamically assigned log level and a unique log ID.

    Args:
        message (str): The message to log.
        level (str): The log level as a string (default is "INFO").
    """
    log_id: str = g.get("log_id", get_log_id())  # Explicit typing
    g.log_id = log_id

    log_message = f"Log ID: {log_id} - {message}"
    log_level = str_to_log_level(level)

    if log_level == logging.CRITICAL:
        app.logger.critical(log_message)
    elif log_level == logging.ERROR:
        app.logger.error(log_message)
    elif log_level == logging.WARNING:
        app.logger.warning(log_message)
    elif log_level == logging.INFO:
        app.logger.info(log_message)
    elif log_level == logging.DEBUG:
        app.logger.debug(log_message)
    elif log_level == logging.NOTSET:
        app.logger.log(logging.NOTSET, log_message)
