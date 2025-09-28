"""
Logging adapter to use Hive centralized logging when available, fallback to local logging.

This module provides a seamless integration layer between EcoSystemiser and Hive's
centralized logging infrastructure while maintaining backward compatibility.
"""

import sys
import logging
from pathlib import Path
from typing import Optional

# Try to import from Hive's centralized logging
try:
    from packages.hive_logging.src.hive_logging import get_logger, setup_logging
    USING_HIVE_LOGGING = True

except ImportError:
    # Fallback to local structlog-based logging
    try:
        from EcoSystemiser.profile_loader.climate.logging_config import get_logger, setup_logging
        USING_HIVE_LOGGING = False
    except ImportError:
        # Last resort: basic Python logging
        def get_logger(name: str) -> logging.Logger:
            """Get a basic logger"""
            return logging.getLogger(name)

        def setup_logging(
            name: str = "ecosystemiser",
            level: str = 'INFO',
            log_to_file: bool = False,
            log_file_path: Optional[str] = None,
            json_format: bool = False
        ):
            """Basic logging setup"""
            logging.basicConfig(
                level=getattr(logging, level.upper(), logging.INFO),
                format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )

        USING_HIVE_LOGGING = False

def initialize_ecosystemiser_logging(
    app_name: str = "ecosystemiser",
    level: str = "INFO",
    log_to_file: bool = True,
    json_format: bool = False
):
    """
    Initialize logging for EcoSystemiser.

    Args:
        app_name: Application name for logging context
        level: Log level
        log_to_file: Whether to log to file
        json_format: Whether to use JSON format
    """
    if USING_HIVE_LOGGING:
        # Use Hive's centralized logging
        setup_logging(
            name=app_name,
            level=level,
            log_to_file=log_to_file,
            log_file_path=f"logs/{app_name}.log",
            json_format=json_format
        )
        logger = get_logger(__name__)
        logger.info(f"EcoSystemiser logging initialized using Hive centralized logging")
    else:
        # Use local logging
        setup_logging(level, 'console' if not json_format else 'json')
        logger = get_logger(__name__)
        logger.info(f"EcoSystemiser logging initialized using local logging")

# Export the main functions
__all__ = ['get_logger', 'setup_logging', 'initialize_ecosystemiser_logging', 'USING_HIVE_LOGGING']