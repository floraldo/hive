"""
Legacy alias for EcoSystemiser error handling.

This module provides backward compatibility by importing from the new core module.
All new code should import directly from ecosystemiser.core.errors.
"""

from typing import Optional

# Import everything from the new core module
from ecosystemiser.core.errors import (
    # Base classes
    EcoSystemiserError,

    # Simulation errors
    SimulationError,
    SimulationConfigError,
    SimulationExecutionError,

    # Profile errors
    ProfileError,
    ProfileLoadError,
    ProfileValidationError,

    # Solver errors
    SolverError,
    OptimizationInfeasibleError,
    SolverConvergenceError,

    # Component errors
    ComponentError,
    ComponentConnectionError,
    ComponentValidationError,

    # Database errors
    DatabaseError,
    DatabaseConnectionError,
    DatabaseTransactionError,

    # Event bus errors
    EventBusError,
    EventPublishError,

    # Error reporter
    EcoSystemiserErrorReporter,
    get_error_reporter
)

# Legacy aliases for common patterns
BaseError = EcoSystemiserError
ConfigurationError = SimulationConfigError
ResourceError = DatabaseError
TimeoutError = SolverConvergenceError

# ValidationError needs special handling for field parameter compatibility
class ValidationError(ComponentValidationError):
    """Legacy ValidationError with field parameter support"""
    def __init__(self, message: str, field: Optional[str] = None, **kwargs):
        # Map 'field' to 'parameter_name' for compatibility
        if field is not None:
            kwargs['parameter_name'] = field
        super().__init__(message, **kwargs)
def handle_error(error, context=None, additional_info=None):
    """Legacy handle_error function"""
    return get_error_reporter().report_error(error, context, additional_info)

# Export main components
__all__ = [
    # New core classes
    "EcoSystemiserError",
    "SimulationError",
    "SimulationConfigError",
    "SimulationExecutionError",
    "ProfileError",
    "ProfileLoadError",
    "ProfileValidationError",
    "SolverError",
    "OptimizationInfeasibleError",
    "SolverConvergenceError",
    "ComponentError",
    "ComponentConnectionError",
    "ComponentValidationError",
    "DatabaseError",
    "DatabaseConnectionError",
    "DatabaseTransactionError",
    "EventBusError",
    "EventPublishError",
    "EcoSystemiserErrorReporter",
    "get_error_reporter",

    # Legacy aliases
    "BaseError",
    "ValidationError",
    "ConfigurationError",
    "ResourceError",
    "TimeoutError",
    "handle_error"
]