from hive_logging import get_logger

logger = get_logger(__name__)

"""
Hive Logging package - Structured logging utilities for Hive applications
"""

from .logger import get_logger, setup_logging

__all__ = ["get_logger", "setup_logging"]
