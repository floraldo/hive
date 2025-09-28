"""
EcoSystemiser-specific error handling implementation.

Extends the generic error handling toolkit with EcoSystemiser capabilities:
- Simulation-specific errors
- Profile loading errors
- Solver optimization errors
- Component validation errors
- EcoSystemiser-specific error reporting
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

try:
    from hive_errors import BaseError, BaseErrorReporter, RecoveryStrategy
except ImportError:
    # Fallback implementation if hive_error_handling is not available
    class BaseError(Exception):
        def __init__(self, message: str, component: str = "unknown", **kwargs):
            super().__init__(message)
            self.message = message
            self.component = component
            self.timestamp = datetime.now(timezone.utc)
            self.error_id = str(uuid.uuid4())
            for key, value in kwargs.items():
                setattr(self, key, value)

    class BaseErrorReporter:
        def report_error(self, error: BaseError):
            logger.error(f"Error in {error.component}: {error.message}")

    class RecoveryStrategy:
        pass


from hive_logging import get_logger

logger = get_logger(__name__)


class EcoSystemiserError(BaseError):
    """
    Base error class for all EcoSystemiser-specific errors.

    Extends the generic BaseError with simulation context and additional
    metadata specific to the EcoSystemiser platform.
    """

    def __init__(
        self,
        message: str,
        component: str = "ecosystemiser",
        operation: Optional[str] = None,
        simulation_id: Optional[str] = None,
        analysis_id: Optional[str] = None,
        optimization_id: Optional[str] = None,
        timestep: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
        recovery_suggestions: Optional[List[str]] = None,
        original_error: Optional[Exception] = None,
    ):
        """
        Initialize an EcoSystemiser error with simulation context.

        Args:
            message: Human-readable error message
            component: Component where error occurred
            operation: Operation being performed
            simulation_id: Active simulation ID if applicable
            analysis_id: Active analysis ID if applicable
            optimization_id: Active optimization ID if applicable
            timestep: Simulation timestep when error occurred
            details: Additional error details
            recovery_suggestions: Steps to recover from error
            original_error: Original exception if wrapped
        """
        # Build details with EcoSystemiser context
        ecosys_details = details or {}

        if simulation_id:
            ecosys_details["simulation_id"] = simulation_id
        if analysis_id:
            ecosys_details["analysis_id"] = analysis_id
        if optimization_id:
            ecosys_details["optimization_id"] = optimization_id
        if timestep is not None:
            ecosys_details["timestep"] = timestep

        super().__init__(
            message=message,
            component=component,
            operation=operation,
            details=ecosys_details,
            recovery_suggestions=recovery_suggestions,
            original_error=original_error,
        )

        # Store EcoSystemiser-specific attributes
        self.simulation_id = simulation_id
        self.analysis_id = analysis_id
        self.optimization_id = optimization_id
        self.timestep = timestep
        self.timestamp = datetime.now(timezone.utc)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary with EcoSystemiser context"""
        data = super().to_dict()
        data["timestamp"] = self.timestamp.isoformat()
        return data


# ===============================================================================
# SIMULATION-SPECIFIC ERRORS
# ===============================================================================


class SimulationError(EcoSystemiserError):
    """Base class for simulation-related errors"""

    def __init__(self, message: str, **kwargs):
        super().__init__(
            message=message, component=kwargs.get("component", "simulation"), **kwargs
        )


class SimulationConfigError(SimulationError):
    """Error in simulation configuration"""

    def __init__(
        self,
        message: str,
        config_key: Optional[str] = None,
        config_value: Any = None,
        **kwargs,
    ):
        details = kwargs.get("details", {})
        if config_key:
            details["config_key"] = config_key
        if config_value is not None:
            details["config_value"] = str(config_value)

        kwargs["details"] = details
        kwargs["recovery_suggestions"] = kwargs.get(
            "recovery_suggestions",
            [
                "Check simulation configuration file",
                "Verify parameter ranges and types",
                "Ensure all required parameters are present",
            ],
        )

        super().__init__(message=message, operation="configuration", **kwargs)


class SimulationExecutionError(SimulationError):
    """Error during simulation execution"""

    def __init__(self, message: str, **kwargs):
        kwargs["recovery_suggestions"] = kwargs.get(
            "recovery_suggestions",
            [
                "Check simulation input data",
                "Verify component connections",
                "Review solver configuration",
                "Check for infeasible constraints",
            ],
        )
        super().__init__(message=message, operation="execution", **kwargs)


# ===============================================================================
# PROFILE LOADING ERRORS
# ===============================================================================


class ProfileError(EcoSystemiserError):
    """Base class for profile-related errors"""

    def __init__(self, message: str, **kwargs):
        super().__init__(
            message=message,
            component=kwargs.get("component", "profile_loader"),
            **kwargs,
        )


class ProfileLoadError(ProfileError):
    """Error loading profile data"""

    def __init__(
        self,
        message: str,
        profile_type: Optional[str] = None,
        source: Optional[str] = None,
        **kwargs,
    ):
        details = kwargs.get("details", {})
        if profile_type:
            details["profile_type"] = profile_type
        if source:
            details["source"] = source

        kwargs["details"] = details
        kwargs["recovery_suggestions"] = kwargs.get(
            "recovery_suggestions",
            [
                "Verify data source availability",
                "Check network connection for API sources",
                "Validate file paths for local sources",
                "Ensure proper API credentials",
            ],
        )

        super().__init__(message=message, operation="load", **kwargs)


class ProfileValidationError(ProfileError):
    """Error validating profile data"""

    def __init__(
        self,
        message: str,
        validation_type: Optional[str] = None,
        failed_checks: Optional[List[str]] = None,
        **kwargs,
    ):
        details = kwargs.get("details", {})
        if validation_type:
            details["validation_type"] = validation_type
        if failed_checks:
            details["failed_checks"] = failed_checks

        kwargs["details"] = details
        kwargs["recovery_suggestions"] = kwargs.get(
            "recovery_suggestions",
            [
                "Check data format and structure",
                "Verify time series continuity",
                "Validate data ranges and units",
                "Ensure quality control thresholds are appropriate",
            ],
        )

        super().__init__(message=message, operation="validation", **kwargs)


# ===============================================================================
# SOLVER AND OPTIMIZATION ERRORS
# ===============================================================================


class SolverError(EcoSystemiserError):
    """Base class for solver-related errors"""

    def __init__(self, message: str, **kwargs):
        super().__init__(
            message=message, component=kwargs.get("component", "solver"), **kwargs
        )


class OptimizationInfeasibleError(SolverError):
    """Error when optimization problem is infeasible"""

    def __init__(
        self,
        message: str,
        solver_type: Optional[str] = None,
        constraints_violated: Optional[List[str]] = None,
        **kwargs,
    ):
        details = kwargs.get("details", {})
        if solver_type:
            details["solver_type"] = solver_type
        if constraints_violated:
            details["constraints_violated"] = constraints_violated

        kwargs["details"] = details
        kwargs["recovery_suggestions"] = kwargs.get(
            "recovery_suggestions",
            [
                "Relax constraint boundaries",
                "Check for conflicting constraints",
                "Verify component capacities",
                "Review demand-supply balance",
                "Consider using a different solver",
            ],
        )

        super().__init__(message=message, operation="optimization", **kwargs)


class SolverConvergenceError(SolverError):
    """Error when solver fails to converge"""

    def __init__(
        self,
        message: str,
        iterations: Optional[int] = None,
        tolerance: Optional[float] = None,
        **kwargs,
    ):
        details = kwargs.get("details", {})
        if iterations is not None:
            details["iterations"] = iterations
        if tolerance is not None:
            details["tolerance"] = tolerance

        kwargs["details"] = details
        kwargs["recovery_suggestions"] = kwargs.get(
            "recovery_suggestions",
            [
                "Increase maximum iterations",
                "Adjust convergence tolerance",
                "Improve initial solution guess",
                "Simplify problem formulation",
                "Use warm-starting if available",
            ],
        )

        super().__init__(message=message, operation="convergence", **kwargs)


# ===============================================================================
# COMPONENT ERRORS
# ===============================================================================


class ComponentError(EcoSystemiserError):
    """Base class for component-related errors"""

    def __init__(
        self,
        message: str,
        component_name: Optional[str] = None,
        component_type: Optional[str] = None,
        **kwargs,
    ):
        details = kwargs.get("details", {})
        if component_name:
            details["component_name"] = component_name
        if component_type:
            details["component_type"] = component_type

        kwargs["details"] = details
        super().__init__(
            message=message,
            component=kwargs.get("component", "component_system"),
            **kwargs,
        )


class ComponentConnectionError(ComponentError):
    """Error in component connections"""

    def __init__(
        self,
        message: str,
        source_component: Optional[str] = None,
        target_component: Optional[str] = None,
        connection_type: Optional[str] = None,
        **kwargs,
    ):
        details = kwargs.get("details", {})
        if source_component:
            details["source_component"] = source_component
        if target_component:
            details["target_component"] = target_component
        if connection_type:
            details["connection_type"] = connection_type

        kwargs["details"] = details
        kwargs["recovery_suggestions"] = kwargs.get(
            "recovery_suggestions",
            [
                "Verify component compatibility",
                "Check connection types match",
                "Ensure components are properly initialized",
                "Review system topology configuration",
            ],
        )

        super().__init__(message=message, operation="connection", **kwargs)


class ComponentValidationError(ComponentError):
    """Error validating component parameters"""

    def __init__(
        self,
        message: str,
        parameter_name: Optional[str] = None,
        parameter_value: Any = None,
        valid_range: Optional[str] = None,
        **kwargs,
    ):
        details = kwargs.get("details", {})
        if parameter_name:
            details["parameter_name"] = parameter_name
        if parameter_value is not None:
            details["parameter_value"] = str(parameter_value)
        if valid_range:
            details["valid_range"] = valid_range

        kwargs["details"] = details
        kwargs["recovery_suggestions"] = kwargs.get(
            "recovery_suggestions",
            [
                "Check parameter value against valid range",
                "Verify parameter units",
                "Ensure parameter type is correct",
                "Review component technical specifications",
            ],
        )

        super().__init__(message=message, operation="validation", **kwargs)


# ===============================================================================
# DATABASE ERRORS
# ===============================================================================


class DatabaseError(EcoSystemiserError):
    """Base class for database-related errors"""

    def __init__(self, message: str, **kwargs):
        super().__init__(
            message=message, component=kwargs.get("component", "database"), **kwargs
        )


class DatabaseConnectionError(DatabaseError):
    """Error connecting to EcoSystemiser database"""

    def __init__(self, message: str, db_path: Optional[str] = None, **kwargs):
        details = kwargs.get("details", {})
        if db_path:
            details["db_path"] = db_path

        kwargs["details"] = details
        kwargs["recovery_suggestions"] = kwargs.get(
            "recovery_suggestions",
            [
                "Check database file exists",
                "Verify file permissions",
                "Ensure database is not locked",
                "Check disk space availability",
            ],
        )

        super().__init__(message=message, operation="connection", **kwargs)


class DatabaseTransactionError(DatabaseError):
    """Error during database transaction"""

    def __init__(self, message: str, transaction_type: Optional[str] = None, **kwargs):
        details = kwargs.get("details", {})
        if transaction_type:
            details["transaction_type"] = transaction_type

        kwargs["details"] = details
        kwargs["recovery_suggestions"] = kwargs.get(
            "recovery_suggestions",
            [
                "Retry transaction",
                "Check for database locks",
                "Verify data integrity",
                "Review transaction isolation level",
            ],
        )

        super().__init__(message=message, operation="transaction", **kwargs)


# ===============================================================================
# EVENT BUS ERRORS
# ===============================================================================


class EventBusError(EcoSystemiserError):
    """Base class for event bus errors"""

    def __init__(self, message: str, **kwargs):
        super().__init__(
            message=message, component=kwargs.get("component", "event_bus"), **kwargs
        )


class EventPublishError(EventBusError):
    """Error publishing event to bus"""

    def __init__(
        self,
        message: str,
        event_type: Optional[str] = None,
        event_id: Optional[str] = None,
        **kwargs,
    ):
        details = kwargs.get("details", {})
        if event_type:
            details["event_type"] = event_type
        if event_id:
            details["event_id"] = event_id

        kwargs["details"] = details
        kwargs["recovery_suggestions"] = kwargs.get(
            "recovery_suggestions",
            [
                "Check event bus connectivity",
                "Verify event format",
                "Ensure event handlers are registered",
                "Review event bus capacity",
            ],
        )

        super().__init__(message=message, operation="publish", **kwargs)


# ===============================================================================
# ERROR REPORTER
# ===============================================================================


class EcoSystemiserErrorReporter(BaseErrorReporter):
    """
    EcoSystemiser-specific error reporter.

    Extends the base error reporter with simulation context tracking
    and EcoSystemiser-specific reporting patterns.
    """

    def __init__(self):
        """Initialize the EcoSystemiser error reporter"""
        super().__init__()
        self.simulation_errors: List[SimulationError] = []
        self.profile_errors: List[ProfileError] = []
        self.solver_errors: List[SolverError] = []
        self.component_errors: List[ComponentError] = []

    def report_error(
        self,
        error: Exception,
        context: Optional[Dict[str, Any]] = None,
        additional_info: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Report an error with EcoSystemiser-specific handling.

        Args:
            error: The error to report
            context: Error context information
            additional_info: Additional information about the error

        Returns:
            Error ID for tracking
        """
        # Generate error ID
        error_id = str(uuid.uuid4())

        # Build error record using parent method
        error_record = self._build_error_record(error, context, additional_info)
        error_record["error_id"] = error_id

        # Update metrics
        self._update_metrics(error_record)

        # Add to history
        self.error_history.append(error_record)

        # Log the error (avoid 'message' key conflict with logging)
        log_record = {k: v for k, v in error_record.items() if k != "message"}
        logger.error(f"EcoSystemiser Error: {error}", extra=log_record)

        # EcoSystemiser-specific categorization and handling
        if isinstance(error, SimulationError):
            self.simulation_errors.append(error)
            self._handle_simulation_error(error)
        elif isinstance(error, ProfileError):
            self.profile_errors.append(error)
            self._handle_profile_error(error)
        elif isinstance(error, SolverError):
            self.solver_errors.append(error)
            self._handle_solver_error(error)
        elif isinstance(error, ComponentError):
            self.component_errors.append(error)
            self._handle_component_error(error)

        return error_id

    def _handle_simulation_error(self, error: SimulationError) -> None:
        """Handle simulation-specific error reporting"""
        if error.simulation_id:
            logger.error(f"Simulation {error.simulation_id} failed: {error.message}")
            # Could trigger simulation recovery or notification

    def _handle_profile_error(self, error: ProfileError) -> None:
        """Handle profile-specific error reporting"""
        logger.warning(f"Profile loading issue: {error.message}")
        # Could trigger fallback to default profiles

    def _handle_solver_error(self, error: SolverError) -> None:
        """Handle solver-specific error reporting"""
        if isinstance(error, OptimizationInfeasibleError):
            logger.critical(f"Optimization infeasible: {error.message}")
            # Could trigger constraint relaxation

    def _handle_component_error(self, error: ComponentError) -> None:
        """Handle component-specific error reporting"""
        logger.error(f"Component error: {error.message}")
        # Could trigger component reconfiguration

    def get_error_summary(self) -> Dict[str, Any]:
        """Get summary of all reported errors"""
        return {
            "total_errors": self.error_counts.get("total", 0),
            "simulation_errors": len(self.simulation_errors),
            "profile_errors": len(self.profile_errors),
            "solver_errors": len(self.solver_errors),
            "component_errors": len(self.component_errors),
            "latest_errors": self.error_history[-10:],  # Last 10 error records
        }


# Global error reporter instance
_error_reporter: Optional[EcoSystemiserErrorReporter] = None


def get_error_reporter() -> EcoSystemiserErrorReporter:
    """Get or create the global EcoSystemiser error reporter"""
    global _error_reporter

    if _error_reporter is None:
        _error_reporter = EcoSystemiserErrorReporter()
        logger.info("EcoSystemiser error reporter initialized")

    return _error_reporter


# Export main classes and functions
__all__ = [
    # Base classes
    "EcoSystemiserError",
    # Simulation errors
    "SimulationError",
    "SimulationConfigError",
    "SimulationExecutionError",
    # Profile errors
    "ProfileError",
    "ProfileLoadError",
    "ProfileValidationError",
    # Solver errors
    "SolverError",
    "OptimizationInfeasibleError",
    "SolverConvergenceError",
    # Component errors
    "ComponentError",
    "ComponentConnectionError",
    "ComponentValidationError",
    # Database errors
    "DatabaseError",
    "DatabaseConnectionError",
    "DatabaseTransactionError",
    # Event bus errors
    "EventBusError",
    "EventPublishError",
    # Reporter
    "EcoSystemiserErrorReporter",
    "get_error_reporter",
    # Legacy aliases for backward compatibility
    "AdapterError",
    "ValidationError",
]


# ===============================================================================
# LEGACY ALIASES FOR BACKWARD COMPATIBILITY
# ===============================================================================

# AdapterError alias for profile loading errors
AdapterError = ProfileLoadError

# ValidationError alias for component validation errors
ValidationError = ComponentValidationError
