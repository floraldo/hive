"""
Generic base exception classes.

These are pure, business-logic-free exception patterns that can be used
to build robust error handling for any system.
"""

from typing import Any, Dict, List, Optional


class BaseError(Exception):
    """
    Generic base exception for any system.

    Contains only the minimal, universal properties that any system error needs:
    - Error message
    - Component identification
    - Operation context
    - Additional details
    - Recovery suggestions
    """

    def __init__(
        self,
        message: str,
        component: str = "unknown",
        operation: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        recovery_suggestions: Optional[List[str]] = None,
        original_error: Optional[Exception] = None,
    ):
        super().__init__(message)
        self.message = message
        self.component = component
        self.operation = operation
        self.details = details or {}
        self.recovery_suggestions = recovery_suggestions or []
        self.original_error = original_error

    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary for serialization"""
        return {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "component": self.component,
            "operation": self.operation,
            "details": self.details,
            "recovery_suggestions": self.recovery_suggestions,
            "original_error": str(self.original_error) if self.original_error else None,
        }


class ConfigurationError(BaseError):
    """Generic configuration-related error"""

    pass


class ConnectionError(BaseError):
    """Generic connection-related error"""

    pass


class ValidationError(BaseError):
    """Generic validation-related error"""

    pass


class TimeoutError(BaseError):
    """Generic timeout-related error"""

    pass


class ResourceError(BaseError):
    """Generic resource-related error (memory, disk, etc.)"""

    pass
