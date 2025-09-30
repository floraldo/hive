from hive_logging import get_logger

logger = get_logger(__name__)

"""Component data repository module."""

from .repository import ComponentRepository

__all__ = ["ComponentRepository"]
