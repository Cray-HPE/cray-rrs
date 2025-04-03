import logging
import os
import uuid
from flask import g
from flask import current_app as app

def get_log_id():
    """ Return a unique string id that can be used to help tie related log entries together. """
    return str(uuid.uuid4())[:8]

"""
def str_to_log_level(level: str) -> int:
    # Mapping of string levels to corresponding logging levels
    name_to_level = {
        'CRITICAL': logging.CRITICAL,
        'FATAL': logging.FATAL,
        'ERROR': logging.ERROR,
        'WARN': logging.WARNING,
        'WARNING': logging.WARNING,
        'INFO': logging.INFO,
        'DEBUG': logging.DEBUG,
        'NOTSET': logging.NOTSET,
    }
    # Default to INFO if the level is not recognized
    return name_to_level.get(level.upper(), logging.INFO)
"""
"""
# Function to log events with automatic log_id generation and dynamic log level
def log_event(message: str, level: str = "INFO"):
    log_id = g.get('log_id')  # Fetch log_id from the request context (Flask's g)
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
"""
    
# Function to log events with automatic log_id generation
def log_event(message, level="INFO"):
    log_id = g.get('log_id')  # Fetch log_id from the request context (Flask's g)
    if not log_id:
        log_id = get_log_id()  # Generate a new log_id if not found in g
        g.log_id = log_id  # Store it in Flask's g object for future use
    log_message = f"Log ID: {log_id} - {message}"
    if level == "INFO":
        app.logger.info(log_message)
    elif level == "ERROR":
        app.logger.error(log_message)
    elif level == "DEBUG":
        app.logger.debug(log_message)
