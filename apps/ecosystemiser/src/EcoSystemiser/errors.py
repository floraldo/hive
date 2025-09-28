"""
EcoSystemiser-specific error handling that inherits from Hive native error system.

Provides domain-specific error types for climate and energy system simulation,
while maintaining consistency with the broader Hive ecosystem.
"""

import uuid
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union
import json

# from hive_error_handling import BaseError as HiveError

class HiveError(Exception):
    """Temporary local HiveError class for build validation"""
    pass
from EcoSystemiser.hive_logging_adapter import get_logger

logger = get_logger(__name__)

class ErrorSeverity(Enum):
    """Error severity levels"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

class ErrorCode(Enum):
    """Standardized error codes for the platform"""
    
    # Data source errors (1xxx)
    SOURCE_UNAVAILABLE = "1001"
    SOURCE_RATE_LIMITED = "1002"
    SOURCE_AUTH_FAILED = "1003"
    SOURCE_INVALID_RESPONSE = "1004"
    SOURCE_TIMEOUT = "1005"
    
    # Validation errors (2xxx)
    VALIDATION_FAILED = "2001"
    INVALID_COORDINATES = "2002"
    INVALID_TIME_PERIOD = "2003"
    INVALID_VARIABLES = "2004"
    DATA_OUT_OF_BOUNDS = "2005"
    
    # Processing errors (3xxx)
    PROCESSING_FAILED = "3001"
    TRANSFORMATION_ERROR = "3002"
    AGGREGATION_ERROR = "3003"
    RESAMPLING_ERROR = "3004"
    GAP_FILLING_ERROR = "3005"
    
    # Cache errors (4xxx)
    CACHE_READ_ERROR = "4001"
    CACHE_WRITE_ERROR = "4002"
    CACHE_INVALIDATION_ERROR = "4003"
    
    # System errors (5xxx)
    INTERNAL_ERROR = "5001"
    MEMORY_ERROR = "5002"
    DISK_ERROR = "5003"
    NETWORK_ERROR = "5004"
    CONFIGURATION_ERROR = "5005"
    
    # Client errors (6xxx)
    BAD_REQUEST = "6001"
    UNAUTHORIZED = "6002"
    FORBIDDEN = "6003"
    NOT_FOUND = "6004"
    METHOD_NOT_ALLOWED = "6005"
    CONFLICT = "6006"
    UNPROCESSABLE_ENTITY = "6007"
    TOO_MANY_REQUESTS = "6008"
    
    # Adapter-specific errors (7xxx)
    ADAPTER_ERROR = "7001"
    DATA_FETCH_ERROR = "7002"
    DATA_PROCESSING_ERROR = "7003"
    AUTHENTICATION_ERROR = "7004"
    DATA_NOT_FOUND = "7005"
    SYSTEM_ERROR = "7006"

@dataclass
class ErrorContext:
    """Context information for an error"""
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    source: Optional[str] = None
    location: Optional[tuple] = None
    variables: Optional[List[str]] = None
    period: Optional[Dict[str, Any]] = None
    user_id: Optional[str] = None
    request_id: Optional[str] = None
    trace_id: Optional[str] = None
    span_id: Optional[str] = None

class ClimateError(HiveError):
    """
    Base exception for climate platform errors.

    Inherits from HiveError to maintain consistency with Hive ecosystem
    while providing climate-specific error handling capabilities.
    """

    def __init__(
        self,
        message: str,
        code: Optional[ErrorCode] = None,
        severity: ErrorSeverity = ErrorSeverity.ERROR,
        context: Optional[ErrorContext] = None,
        cause: Optional[Exception] = None,
        retriable: bool = False,
        suggested_action: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        **kwargs
    ):
        # Initialize context if not provided
        if context is None:
            context = ErrorContext()

        # Ensure code is an ErrorCode enum
        if code is None:
            code = ErrorCode.INTERNAL_ERROR
        elif isinstance(code, str):
            try:
                code = ErrorCode(code)
            except (ValueError, KeyError):
                code = ErrorCode.INTERNAL_ERROR

        # Prepare details dictionary for HiveError
        hive_details = details or {}
        hive_details.update({
            'code': code.value,
            'severity': severity.value,
            'retriable': retriable,
            'correlation_id': context.correlation_id,
            'timestamp': context.timestamp
        })

        if suggested_action:
            hive_details['suggested_action'] = suggested_action
        if context.source:
            hive_details['source'] = context.source

        # Initialize HiveError with climate-specific context
        super().__init__(
            message=message,
            component="ecosystemiser",
            operation=kwargs.get('operation', 'unknown'),
            details=hive_details,
            recovery_suggestions=[suggested_action] if suggested_action else None
        )

        # Store climate-specific attributes
        self.code = code
        self.severity = severity
        self.context = context
        self.cause = cause
        self.retriable = retriable
        self.suggested_action = suggested_action

        # Log the error with appropriate level
        self._log_error()

    def _log_error(self):
        """Log error with appropriate level"""
        log_message = f"[{self.context.correlation_id}] Error {self.code.value}: {self.message}"

        if self.severity == ErrorSeverity.CRITICAL:
            logger.critical(log_message, exc_info=self.cause)
        elif self.severity == ErrorSeverity.ERROR:
            logger.error(log_message, exc_info=self.cause)
        elif self.severity == ErrorSeverity.WARNING:
            logger.warning(log_message)
        else:
            logger.info(log_message)

    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary for JSON serialization"""
        base_dict = super().to_dict()

        # Add climate-specific error information
        climate_dict = {
            'error': {
                'code': self.code.value,
                'message': self.message,
                'severity': self.severity.value,
                'retriable': self.retriable,
                'correlation_id': self.context.correlation_id,
                'timestamp': self.context.timestamp,
                'hive_component': base_dict.get('component', 'ecosystemiser'),
                'hive_operation': base_dict.get('operation', 'unknown')
            }
        }

        if self.suggested_action:
            climate_dict['error']['suggested_action'] = self.suggested_action

        if hasattr(self, 'details') and self.details:
            climate_dict['error']['details'] = {
                k: v for k, v in self.details.items()
                if k not in ['code', 'severity', 'retriable', 'correlation_id', 'timestamp']
            }

        if self.context.source:
            climate_dict['error']['source'] = self.context.source

        if self.cause:
            climate_dict['error']['cause'] = str(self.cause)

        return climate_dict

    def to_json(self) -> str:
        """Convert error to JSON string"""
        return json.dumps(self.to_dict(), indent=2)

    def __str__(self):
        return f"[{self.code.value}] {self.message} (correlation_id: {self.context.correlation_id})"

# Specific error types

class DataSourceError(ClimateError):
    """Errors related to external data sources"""
    
    def __init__(
        self,
        message: str,
        source: str,
        code: ErrorCode = ErrorCode.SOURCE_UNAVAILABLE,
        **kwargs
    ):
        context = kwargs.pop('context', ErrorContext())
        context.source = source
        
        super().__init__(
            code=code,
            message=message,
            context=context,
            retriable=code in [
                ErrorCode.SOURCE_UNAVAILABLE,
                ErrorCode.SOURCE_RATE_LIMITED,
                ErrorCode.SOURCE_TIMEOUT
            ],
            **kwargs
        )

class ValidationError(ClimateError):
    """Errors related to data validation"""
    
    def __init__(
        self,
        message: str,
        code: ErrorCode = ErrorCode.VALIDATION_FAILED,
        **kwargs
    ):
        super().__init__(
            code=code,
            message=message,
            severity=ErrorSeverity.WARNING,
            retriable=False,
            **kwargs
        )

class ProcessingError(ClimateError):
    """Errors during data processing"""
    
    def __init__(
        self,
        message: str,
        code: ErrorCode = ErrorCode.PROCESSING_FAILED,
        **kwargs
    ):
        super().__init__(
            code=code,
            message=message,
            retriable=False,
            **kwargs
        )

class RateLimitError(DataSourceError):
    """Rate limit exceeded error"""
    
    def __init__(
        self,
        source: str,
        retry_after: Optional[int] = None,
        **kwargs
    ):
        message = f"Rate limit exceeded for {source}"
        if retry_after:
            message += f". Retry after {retry_after} seconds"
        
        details = kwargs.pop('details', {})
        details['retry_after'] = retry_after
        
        super().__init__(
            message=message,
            source=source,
            code=ErrorCode.SOURCE_RATE_LIMITED,
            severity=ErrorSeverity.WARNING,
            details=details,
            suggested_action="Wait before retrying or reduce request rate",
            **kwargs
        )

class InvalidLocationError(ValidationError):
    """Invalid geographic coordinates"""
    
    def __init__(
        self,
        latitude: float,
        longitude: float,
        **kwargs
    ):
        message = f"Invalid coordinates: ({latitude}, {longitude})"
        
        super().__init__(
            message=message,
            code=ErrorCode.INVALID_COORDINATES,
            details={'latitude': latitude, 'longitude': longitude},
            suggested_action="Ensure latitude is between -90 and 90, longitude between -180 and 180",
            **kwargs
        )

class InvalidPeriodError(ValidationError):
    """Invalid time period"""
    
    def __init__(
        self,
        period: Dict[str, Any],
        reason: str,
        **kwargs
    ):
        message = f"Invalid time period: {reason}"
        
        super().__init__(
            message=message,
            code=ErrorCode.INVALID_TIME_PERIOD,
            details={'period': period, 'reason': reason},
            suggested_action="Check period format and ensure dates are valid",
            **kwargs
        )

class TemporalError(ValidationError):
    """Temporal validation error"""
    
    def __init__(
        self,
        message: str,
        **kwargs
    ):
        super().__init__(
            message=message,
            code=ErrorCode.INVALID_TIME_PERIOD,
            **kwargs
        )

class LocationError(ValidationError):
    """Location resolution or validation error"""
    
    def __init__(
        self,
        message: str,
        location: Optional[str] = None,
        **kwargs
    ):
        details = kwargs.pop('details', {})
        if location:
            details['location'] = location
        
        super().__init__(
            message=message,
            code=ErrorCode.INVALID_COORDINATES,
            details=details if details else None,
            **kwargs
        )

@dataclass
class AdapterError(ClimateError):
    """Base exception for adapter-related errors"""
    adapter_name: str = field(default="")
    
    def __post_init__(self):
        """Add adapter name to details"""
        super().__post_init__()
        if self.details is None:
            self.details = {}
        self.details['adapter'] = self.adapter_name

@dataclass
class DataFetchError(AdapterError):
    """Error fetching data from external source"""
    url: Optional[str] = field(default=None)
    status_code: Optional[int] = field(default=None)
    
    def __post_init__(self):
        """Add URL and status code to details"""
        super().__post_init__()
        if self.url:
            self.details['url'] = self.url
        if self.status_code:
            self.details['status_code'] = self.status_code

@dataclass
class DataParseError(AdapterError):
    """Error parsing data from external source"""
    field_name: Optional[str] = field(default=None)
    
    def __post_init__(self):
        """Add field to details"""
        super().__post_init__()
        if self.field_name:
            self.details['field'] = self.field_name

class AuthenticationError(AdapterError):
    """Error with adapter authentication"""
    
    def __init__(self, adapter_name: str, message: str, **kwargs):
        super().__init__(
            code=ErrorCode.AUTHENTICATION_ERROR,
            message=message,
            adapter_name=adapter_name,
            severity=ErrorSeverity.ERROR,
            suggested_action=kwargs.get('suggested_action', "Check API key or credentials configuration"),
            **{k: v for k, v in kwargs.items() if k not in ['suggested_action']}
        )

class DataNotAvailableError(AdapterError):
    """Data not available for requested parameters"""
    
    def __init__(self, adapter_name: str, message: str, **kwargs):
        super().__init__(
            code=ErrorCode.DATA_NOT_FOUND,
            message=message,
            adapter_name=adapter_name,
            severity=ErrorSeverity.WARNING,
            suggested_action=kwargs.get('suggested_action', "Try a different time period or location"),
            **{k: v for k, v in kwargs.items() if k not in ['suggested_action']}
        )

class ErrorHandler:
    """
    Central error handler for the platform.
    
    Provides unified error handling, conversion, and response generation.
    """
    
    @staticmethod
    def handle_exception(
        exception: Exception,
        context: Optional[ErrorContext] = None
    ) -> ClimateError:
        """
        Convert any exception to a ClimateError.
        
        Args:
            exception: The exception to handle
            context: Optional error context
            
        Returns:
            ClimateError instance
        """
        if isinstance(exception, ClimateError):
            # Already a ClimateError, just ensure context
            if context and not exception.context:
                exception.context = context
            return exception
        
        # Map common exceptions to ClimateError
        if isinstance(exception, ValueError):
            return ValidationError(
                message=str(exception),
                context=context,
                cause=exception
            )
        
        if isinstance(exception, TimeoutError):
            return DataSourceError(
                message="Request timed out",
                source="unknown",
                code=ErrorCode.SOURCE_TIMEOUT,
                context=context,
                cause=exception
            )
        
        if isinstance(exception, ConnectionError):
            return ClimateError(
                code=ErrorCode.NETWORK_ERROR,
                message="Network connection error",
                severity=ErrorSeverity.ERROR,
                context=context,
                cause=exception,
                retriable=True,
                suggested_action="Check network connectivity and retry"
            )
        
        if isinstance(exception, MemoryError):
            return ClimateError(
                code=ErrorCode.MEMORY_ERROR,
                message="Insufficient memory",
                severity=ErrorSeverity.CRITICAL,
                context=context,
                cause=exception,
                suggested_action="Reduce request size or increase available memory"
            )
        
        # Default: wrap as internal error
        return ClimateError(
            code=ErrorCode.INTERNAL_ERROR,
            message=f"Unexpected error: {str(exception)}",
            severity=ErrorSeverity.ERROR,
            context=context,
            cause=exception,
            details={'exception_type': type(exception).__name__}
        )
    
    @staticmethod
    def create_error_response(
        error: Union[ClimateError, Exception],
        status_code: int = 500
    ) -> Dict[str, Any]:
        """
        Create API error response.
        
        Args:
            error: The error to convert
            status_code: HTTP status code
            
        Returns:
            Error response dictionary
        """
        if not isinstance(error, ClimateError):
            error = ErrorHandler.handle_exception(error)
        
        response = error.to_dict()
        response['status_code'] = status_code
        
        return response
    
    @staticmethod
    def log_and_handle(
        exception: Exception,
        context: Optional[ErrorContext] = None,
        reraise: bool = True
    ) -> Optional[ClimateError]:
        """
        Log exception and optionally reraise as ClimateError.
        
        Args:
            exception: The exception to handle
            context: Optional error context
            reraise: Whether to reraise the exception
            
        Returns:
            ClimateError if not reraising
            
        Raises:
            ClimateError if reraise is True
        """
        climate_error = ErrorHandler.handle_exception(exception, context)
        
        if reraise:
            raise climate_error
        
        return climate_error

# Correlation ID management

class CorrelationIDMiddleware:
    """
    Middleware for managing correlation IDs across requests.
    
    Ensures every request has a correlation ID for tracing.
    """
    
    HEADER_NAME = "X-Correlation-ID"
    
    @staticmethod
    def get_or_create_correlation_id(
        headers: Optional[Dict[str, str]] = None
    ) -> str:
        """
        Get correlation ID from headers or create new one.
        
        Args:
            headers: Request headers
            
        Returns:
            Correlation ID
        """
        if headers and CorrelationIDMiddleware.HEADER_NAME in headers:
            return headers[CorrelationIDMiddleware.HEADER_NAME]
        
        return str(uuid.uuid4())
    
    @staticmethod
    def inject_correlation_id(
        headers: Dict[str, str],
        correlation_id: str
    ) -> Dict[str, str]:
        """
        Inject correlation ID into headers.
        
        Args:
            headers: Headers dictionary
            correlation_id: Correlation ID to inject
            
        Returns:
            Updated headers
        """
        headers[CorrelationIDMiddleware.HEADER_NAME] = correlation_id
        return headers