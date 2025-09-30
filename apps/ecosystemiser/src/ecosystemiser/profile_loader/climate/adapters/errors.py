from __future__ import annotations

from hive_errors import BaseError
from hive_logging import get_logger

logger = get_logger(__name__)


"""Local error classes for climate adapters to avoid circular imports"""

from typing import Any


class AdapterError(Exception):
    """Base error class for adapter-specific errors"""

    def __init__(
        self,
        message: str,
        adapter_name: str | None = None,
        details: dict[str, Any] | None = None,
        **kwargs,
    ):
        super().__init__(message)
        self.message = message
        self.adapter_name = adapter_name
        self.details = details or {}

        # Store additional fields
        for key, value in kwargs.items():
            setattr(self, key, value)


class DataFetchError(BaseError):
    """Error fetching data from a source"""

    def __init__(
        self,
        adapter_name: str,
        message: str,
        details: dict[str, Any] | None = None,
        suggested_action: str | None = None,
        **kwargs,
    ):
        super().__init__(message, adapter_name, details, **kwargs)
        self.suggested_action = suggested_action


class DataParseError(BaseError):
    """Error parsing response data"""

    def __init__(
        self,
        adapter_name: str,
        message: str,
        field: str | None = None,
        details: dict[str, Any] | None = None,
        **kwargs,
    ):
        super().__init__(message, adapter_name, details, **kwargs)
        self.field = field


class ValidationError(BaseError):
    """Error validating request parameters or data"""

    def __init__(
        self,
        message: str,
        field: str | None = None,
        value: Any | None = None,
        recovery_suggestion: str | None = None,
        **kwargs,
    ):
        super().__init__(message, **kwargs)
        self.field = field
        self.value = value
        self.recovery_suggestion = recovery_suggestion


# For backward compatibility with imports
