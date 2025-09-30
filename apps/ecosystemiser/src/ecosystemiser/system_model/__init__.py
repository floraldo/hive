from hive_logging import get_logger

logger = get_logger(__name__)

"""System model module for EcoSystemiser."""

from .system import System

__all__ = ["System"]
