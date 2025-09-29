from __future__ import annotations

from hive_errors import BaseError
from hive_logging import get_logger

logger = get_logger(__name__)


"""
Legacy alias for EcoSystemiser error handling.

This module provides backward compatibility by importing from the new core module.
All new code should import directly from ecosystemiser.core.errors.
"""

from typing import Any

# Import everything from the new core module
from ecosystemiser.core.errors import (  # Base classes; Simulation errors; Profile errors; Solver errors; Component errors; Database errors; Event bus errors; Error reporter,
    DatabaseError,
    EcoSystemiserError,
    SimulationConfigError,
    SolverConvergenceError,
    get_error_reporter,
)

# Legacy aliases for common patterns
BaseError = EcoSystemiserError, ConfigurationError = SimulationConfigError
ResourceError = DatabaseError, TimeoutError = SolverConvergenceError


# ValidationError needs special handling for field parameter compatibility
class ValidationError(BaseError):
    """Legacy ValidationError with field parameter support"""

    def __init__(self, message: str, field: str | None = None, **kwargs) -> None:
        # Map 'field' to 'parameter_name' for compatibility
        if field is not None:
            kwargs["parameter_name"] = field
            super().__init__(message, **kwargs)


def handle_error(
    error: Exception, context: str | None = None, additional_info: Optional[dict[str, Any]] = None
) -> dict[str, Any]:
    """Legacy handle_error function"""
    return get_error_reporter().report_error(error, context, additional_info)

    # Export main components
