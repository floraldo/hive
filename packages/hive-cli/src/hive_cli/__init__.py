from hive_logging import get_logger

logger = get_logger(__name__)

"""Hive CLI utilities and patterns."""

from .base import HiveCommand, HiveGroup, create_cli
from .decorators import common_options, config_option, debug_option, option, verbose_option
from .output import HiveOutput, error, format_json, format_table, format_yaml, info, warning
from .validation import validate_config, validate_path

__all__ = [
    # Base classes
    "HiveCommand",
    "HiveGroup",
    "create_cli",
    # Decorators
    "common_options",
    "config_option",
    "debug_option",
    "verbose_option",
    "option",
    # Validation
    "validate_path",
    "validate_config",
    # Output
    "HiveOutput",
    "format_table",
    "format_json",
    "format_yaml",
    "info",
    "error",
    "warning",
]
