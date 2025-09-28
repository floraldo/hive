"""
Generic error handling and reporting toolkit.

Provides reusable components for building robust error management:
- Base exception classes
- Error reporting patterns
- Recovery mechanisms
- Metrics collection

This package contains NO business logic - it's a generic toolkit
that can be used to build error handling for any system.
"""

from .base_exceptions import BaseError
from .error_reporter import BaseErrorReporter
from .recovery import RecoveryStatus, RecoveryStrategy

__all__ = ["BaseError", "BaseErrorReporter", "RecoveryStrategy", "RecoveryStatus"]
