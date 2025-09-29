from hive_logging import get_logger

logger = get_logger(__name__)

"""
Structured, configurable logging utilities for Hive applications.
"""

import logging
import logging.handlers
import os
import sys
from pathlib import Path
from typing import Optional

# Import the JSON formatter if the library is available
try:
    from pythonjsonlogger import jsonlogger

    HAS_JSON_LOGGER = True
except ImportError:
    jsonlogger = None
    HAS_JSON_LOGGER = False


def setup_logging(
    name: str,
    level: str = "INFO",
    log_to_file: bool = False,
    log_file_path: Optional[str] = None,
    json_format: bool = False,
) -> None:
    """
    Configure the root logger for an application. This should be called once at startup.

    Args:
        name: The name of the application, used for the log file name if not provided.
        level: The log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        log_to_file: If True, logs will be written to a file.
        log_file_path: The full path to the log file. If None, defaults to 'logs/{name}.log'.
        json_format: If True, logs will be formatted as JSON.
    """
    log_level = os.environ.get("LOG_LEVEL", level).upper()

    # Get the root logger
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, log_level, logging.INFO))

    # Clear any existing handlers to avoid duplicates
    if logger.hasHandlers():
        logger.handlers.clear()

    # Define the formatter
    if json_format and HAS_JSON_LOGGER:
        # JSON format: {"timestamp": "...", "level": "...", "name": "...", "message": "..."}
        formatter = jsonlogger.JsonFormatter("%(asctime)s %(name)s %(levelname)s %(message)s")
    else:
        if json_format and not HAS_JSON_LOGGER:
            logger.warning(
                "JSON logging requested but python-json-logger not available, falling back to standard format"
            )
        formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    # Console Handler (always on)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File Handler (optional)
    if log_to_file:
        if not log_file_path:
            log_file_path = f"logs/{name}.log"

        # Ensure log directory exists
        log_dir = Path(log_file_path).parent
        log_dir.mkdir(parents=True, exist_ok=True)

        # Use a rotating file handler to prevent log files from growing infinitely
        file_handler = logging.handlers.RotatingFileHandler(
            log_file_path,
            maxBytes=(10 * 1024 * 1024),  # 10 MB per file
            backupCount=5,  # Keep 5 backup files
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    logging.info(
        f"Logging configured for '{name}' at level {log_level}. File logging: {log_to_file}, JSON format: {json_format and HAS_JSON_LOGGER}"
    )


def get_logger(name: str, level: Optional[str] = None) -> logging.Logger:
    """
    Get a logger instance. Assumes setup_logging() has already been called for applications,
    or provides basic configuration for standalone use.

    Args:
        name: Logger name (usually __name__ of the calling module)
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL) - for backward compatibility

    Returns:
        Configured logger instance.
    """
    logger = logging.getLogger(name)

    # If this is being called standalone (no root logger configured),
    # provide basic configuration for backward compatibility
    if not logging.getLogger().hasHandlers():
        # Set level from parameter or environment
        log_level = level or os.environ.get("LOG_LEVEL", "INFO").upper()
        logger.setLevel(getattr(logging, log_level, logging.INFO))

        # Create console handler
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logger.level)

        # Create formatter
        formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        handler.setFormatter(formatter)

        # Add handler to logger
        logger.addHandler(handler)

    return logger
