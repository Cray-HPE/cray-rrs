"""
This module provides logging utilities to generate and manage log IDs,
convert log levels from strings to integers, and log events in a consistent format.
"""

import logging
import uuid
from flask import g
from flask import current_app as app


def get_log_id():
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
    # Mapping of string levels to corresponding logging levels
    name_to_level = {
        "CRITICAL": logging.CRITICAL,
        "FATAL": logging.FATAL,
        "ERROR": logging.ERROR,
        "WARN": logging.WARNING,
        "WARNING": logging.WARNING,
        "INFO": logging.INFO,
        "DEBUG": logging.DEBUG,
        "NOTSET": logging.NOTSET,
    }
    # Default to INFO if the level is not recognized
    return name_to_level.get(level.upper(), logging.INFO)


def log_event(message: str, level: str = "INFO"):
    """
    Log an event with a dynamically assigned log level and a unique log ID.

    This function will either retrieve an existing log ID from Flask's g object
    or generate a new one if none exists. It logs the event with the appropriate
    log level and the associated log ID.

    Args:
        message (str): The message to log.
        level (str): The log level as a string (default is "INFO").
    """
    log_id = g.get("log_id")  # Fetch log_id from the request context (Flask's g)
    if not log_id:
        log_id = get_log_id()  # Generate a new log_id if not found in g
        g.log_id = log_id  # Store it in Flask's g object for future use

    log_message = f"Log ID: {log_id} - {message}"

    # Convert string log level to corresponding logging level integer
    log_level = str_to_log_level(level)

    # Log based on the determined level
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
