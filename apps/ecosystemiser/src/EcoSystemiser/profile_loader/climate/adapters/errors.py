"""Local error classes for climate adapters to avoid circular imports"""

from typing import Optional, List, Dict, Any


class AdapterError(Exception):
    """Base error class for adapter-specific errors"""

    def __init__(
        self,
        message: str,
        adapter_name: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        **kwargs
    ):
        super().__init__(message)
        self.message = message
        self.adapter_name = adapter_name
        self.details = details or {}

        # Store additional fields
        for key, value in kwargs.items():
            setattr(self, key, value)


class DataFetchError(AdapterError):
    """Error fetching data from a source"""

    def __init__(
        self,
        adapter_name: str,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        suggested_action: Optional[str] = None,
        **kwargs
    ):
        super().__init__(message, adapter_name, details, **kwargs)
        self.suggested_action = suggested_action


class DataParseError(AdapterError):
    """Error parsing response data"""

    def __init__(
        self,
        adapter_name: str,
        message: str,
        field: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        **kwargs
    ):
        super().__init__(message, adapter_name, details, **kwargs)
        self.field = field


class ValidationError(AdapterError):
    """Error validating request parameters or data"""

    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        value: Optional[Any] = None,
        recovery_suggestion: Optional[str] = None,
        **kwargs
    ):
        super().__init__(message, **kwargs)
        self.field = field
        self.value = value
        self.recovery_suggestion = recovery_suggestion


# For backward compatibility with imports
ProfileLoadError = DataFetchError
ProfileValidationError = DataParseError