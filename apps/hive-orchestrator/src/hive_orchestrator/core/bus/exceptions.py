from hive_errors import BaseError
from hive_logging import get_logger

logger = get_logger(__name__)


"""
Event Bus specific exceptions

Provides structured exception hierarchy for event bus operations
with proper error context and recovery strategies.
"""

from typing import Any, Dict, Optional

from hive_errors import HiveError


class EventBusError(BaseError):
    """Base exception for event bus operations"""

    def __init__(
        self,
        message: str,
        event_id: Optional[str] = None,
        event_type: Optional[str] = None,
        source_agent: Optional[str] = None,
        original_error: Optional[Exception] = None,
        context: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message, original_error=original_error, context=context)
        self.event_id = event_id
        self.event_type = event_type
        self.source_agent = source_agent


class EventPublishError(BaseError):
    """Exception raised when event publishing fails"""

    def __init__(
        self,
        message: str,
        event_id: Optional[str] = None,
        event_type: Optional[str] = None,
        source_agent: Optional[str] = None,
        original_error: Optional[Exception] = None,
    ):
        super().__init__(
            message=f"Failed to publish event: {message}",
            event_id=event_id,
            event_type=event_type,
            source_agent=source_agent,
            original_error=original_error,
        )


class EventSubscribeError(BaseError):
    """Exception raised when event subscription fails"""

    def __init__(
        self,
        message: str,
        pattern: Optional[str] = None,
        subscriber_name: Optional[str] = None,
        original_error: Optional[Exception] = None,
    ):
        super().__init__(
            message=f"Failed to subscribe to events: {message}",
            original_error=original_error,
            context={"pattern": pattern, "subscriber_name": subscriber_name},
        )
        self.pattern = pattern
        self.subscriber_name = subscriber_name


class EventProcessingError(BaseError):
    """Exception raised when event processing fails"""

    def __init__(
        self,
        message: str,
        event_id: Optional[str] = None,
        event_type: Optional[str] = None,
        subscriber_name: Optional[str] = None,
        original_error: Optional[Exception] = None,
    ):
        super().__init__(
            message=f"Failed to process event: {message}",
            event_id=event_id,
            event_type=event_type,
            original_error=original_error,
            context={"subscriber_name": subscriber_name},
        )
        self.subscriber_name = subscriber_name


class EventStorageError(BaseError):
    """Exception raised when event storage operations fail"""

    def __init__(
        self,
        message: str,
        operation: Optional[str] = None,
        original_error: Optional[Exception] = None,
    ):
        super().__init__(
            message=f"Event storage operation failed: {message}",
            original_error=original_error,
            context={"operation": operation},
        )
        self.operation = operation


class EventNotFoundError(BaseError):
    """Exception raised when requested event is not found"""

    def __init__(self, event_id: str, message: Optional[str] = None) -> None:
        if not message:
            message = f"Event with ID {event_id} not found"

        super().__init__(message=message, event_id=event_id)
