"""
DEPRECATED: Legacy logging adapter - use hive_logging directly.

This module is deprecated and maintained only for backward compatibility.
New code should import directly from hive_logging package.
"""

import warnings

# Direct re-export from hive_logging
from hive_logging import get_logger, setup_logging

# Issue deprecation warning
warnings.warn(
    "ecosystemiser.hive_logging_adapter is deprecated. "
    "Use 'from hive_logging import get_logger' instead.",
    DeprecationWarning,
    stacklevel=2
)

# Legacy compatibility exports
USING_HIVE_LOGGING = True

def initialize_ecosystemiser_logging(
    app_name: str = "ecosystemiser",
    level: str = "INFO",
    log_to_file: bool = True,
    json_format: bool = False
):
    """
    DEPRECATED: Use hive_logging.setup_logging directly.
    """
    warnings.warn(
        "initialize_ecosystemiser_logging is deprecated. "
        "Use hive_logging.setup_logging directly.",
        DeprecationWarning,
        stacklevel=2
    )

    setup_logging(
        name=app_name,
        level=level,
        log_to_file=log_to_file,
        log_file_path=f"logs/{app_name}.log"
    )

# Export the main functions
__all__ = ['get_logger', 'setup_logging', 'initialize_ecosystemiser_logging', 'USING_HIVE_LOGGING']