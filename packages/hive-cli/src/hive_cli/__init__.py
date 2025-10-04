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
    # Output
    "HiveOutput",
    # Decorators
    "common_options",
    "config_option",
    "create_cli",
    "debug_option",
    "error",
    "format_json",
    "format_table",
    "format_yaml",
    "info",
    "option",
    "validate_config",
    # Validation
    "validate_path",
    "verbose_option",
    "warning",
]
