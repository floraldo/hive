"""
EcoSystemiser Logging Configuration.

Extends hive-logging with EcoSystemiser-specific structured logging while maintaining
compatibility with the existing structlog implementation.
"""

from typing import Optional

from hive_logging import get_logger as get_hive_logger, setup_logging as setup_hive_logging

# Import the existing structlog configuration for backward compatibility
from ecosystemiser.profile_loader.climate.logging_config import (
    AdapterContextProcessor,
    CorrelationIDProcessor,
    ErrorContextProcessor,
    LoggingContext,
    PerformanceProcessor,
    clear_context,
    log_with_context,
    set_correlation_id,
    set_request_id,
    setup_logging as setup_structlog_logging,
)

# Re-export structlog logger for EcoSystemiser components that need it
try:
    import structlog
    from ecosystemiser.profile_loader.climate.logging_config import get_logger as get_structlog_logger

    STRUCTLOG_AVAILABLE = True
except ImportError:
    STRUCTLOG_AVAILABLE = False


def setup_logging(
    log_level: Optional[str] = None, log_format: Optional[str] = None, use_structlog: bool = True
) -> None:
    """
    Setup logging for EcoSystemiser with choice between hive-logging and structlog.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_format: Output format ('json' or 'console')
        use_structlog: Whether to use structlog (True) or hive-logging (False)
    """
    if use_structlog and STRUCTLOG_AVAILABLE:
        # Use existing structlog configuration for advanced features
        setup_structlog_logging(log_level=log_level, log_format=log_format)
    else:
        # Fall back to hive-logging for consistency with other apps
        setup_hive_logging(
            name="ecosystemiser", level=log_level or "INFO", log_to_file=True, json_format=(log_format == "json")
        )


def get_logger(name: str, use_structlog: Optional[bool] = None):
    """
    Get a logger instance with automatic selection between structlog and hive-logging.

    Args:
        name: Logger name (usually __name__)
        use_structlog: Force structlog (True) or hive-logging (False).
                      If None, auto-detect based on module name.

    Returns:
        Logger instance (either structlog or standard logging)
    """
    # Auto-detect based on module name if not specified
    if use_structlog is None:
        # Use structlog for climate and profile_loader modules for backward compatibility
        use_structlog = any(component in name for component in ["profile_loader", "climate", "adapters", "processing"])

    if use_structlog and STRUCTLOG_AVAILABLE:
        return get_structlog_logger(name)
    else:
        return get_hive_logger(name)


# Re-export context management functions for structured logging
__all__ = [
    "setup_logging",
    "get_logger",
    "LoggingContext",
    "set_correlation_id",
    "set_request_id",
    "clear_context",
    "log_with_context",
    "STRUCTLOG_AVAILABLE",
]
