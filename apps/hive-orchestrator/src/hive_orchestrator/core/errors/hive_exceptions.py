from __future__ import annotations

from hive_logging import get_logger

logger = get_logger(__name__)

"""
Hive-specific exception classes.

Extends the generic error handling toolkit with Hive orchestration errors.
These contain the business logic for Hive-specific error scenarios.
"""

from typing import Any, Dict, List

from hive_errors import BaseError


class HiveError(BaseError):
    """Base class for all Hive-specific errors"""

    def __init__(
        self
        message: str
        component: str = "hive-orchestrator"
        operation: str | None = None
        details: Optional[Dict[str, Any]] = None
        recovery_suggestions: Optional[List[str]] = None
        original_error: Exception | None = None
    ):
        super().__init__(
            message=message
            component=component
            operation=operation
            details=details
            recovery_suggestions=recovery_suggestions
            original_error=original_error
        )


# Task Management Errors
class TaskError(BaseError):
    """Base class for task-related errors"""

    pass


class TaskCreationError(BaseError):
    """Error during task creation"""

    def __init__(self, task_description: str, reason: str, **kwargs) -> None:
        super().__init__(
            message=f"Failed to create task '{task_description}': {reason}"
            operation="create_task"
            recovery_suggestions=[
                "Check task description format"
                "Verify required parameters"
                "Check system resources"
            ]
            **kwargs
        )


class TaskExecutionError(BaseError):
    """Error during task execution"""

    def __init__(self, task_id: str, worker_id: str, reason: str, **kwargs) -> None:
        super().__init__(
            message=f"Task {task_id} failed on worker {worker_id}: {reason}"
            operation="execute_task"
            details={"task_id": task_id, "worker_id": worker_id}
            recovery_suggestions=[
                "Retry task on different worker"
                "Check worker health status"
                "Reduce task complexity"
                "Check system resources"
            ]
            **kwargs
        )


class TaskTimeoutError(BaseError):
    """Error when task exceeds time limit"""

    def __init__(self, task_id: str, timeout_seconds: int, **kwargs) -> None:
        super().__init__(
            message=f"Task {task_id} timed out after {timeout_seconds} seconds"
            operation="execute_task"
            details={"task_id": task_id, "timeout_seconds": timeout_seconds}
            recovery_suggestions=[
                "Increase task timeout"
                "Break task into smaller parts"
                "Check for infinite loops"
                "Optimize task implementation"
            ]
            **kwargs
        )


# Worker Management Errors
class WorkerError(BaseError):
    """Base class for worker-related errors"""

    pass


class WorkerSpawnError(BaseError):
    """Error spawning a new worker"""

    def __init__(self, worker_type: str, reason: str, **kwargs) -> None:
        super().__init__(
            message=f"Failed to spawn {worker_type} worker: {reason}"
            operation="spawn_worker"
            details={"worker_type": worker_type}
            recovery_suggestions=[
                "Check system resources"
                "Verify worker configuration"
                "Check network connectivity"
                "Restart orchestrator service"
            ]
            **kwargs
        )


class WorkerCommunicationError(BaseError):
    """Error communicating with worker"""

    def __init__(self, worker_id: str, operation: str, reason: str, **kwargs) -> None:
        super().__init__(
            message=f"Communication failed with worker {worker_id} during {operation}: {reason}"
            operation="worker_communication"
            details={"worker_id": worker_id, "failed_operation": operation}
            recovery_suggestions=[
                "Check worker health status"
                "Retry communication"
                "Restart worker"
                "Check network connectivity"
            ]
            **kwargs
        )


class WorkerOverloadError(BaseError):
    """Error when worker is overloaded"""

    def __init__(self, worker_id: str, current_load: int, max_load: int, **kwargs) -> None:
        super().__init__(
            message=f"Worker {worker_id} overloaded: {current_load}/{max_load} tasks"
            operation="assign_task"
            details={
                "worker_id": worker_id
                "current_load": current_load
                "max_load": max_load
            }
            recovery_suggestions=[
                "Spawn additional workers"
                "Redistribute tasks"
                "Increase worker capacity"
                "Implement load balancing"
            ]
            **kwargs
        )


# Event Bus Errors
class EventBusError(BaseError):
    """Base class for event bus errors"""

    pass


class EventPublishError(BaseError):
    """Error publishing event to bus"""

    def __init__(self, event_type: str, reason: str, **kwargs) -> None:
        super().__init__(
            message=f"Failed to publish {event_type} event: {reason}"
            operation="publish_event"
            details={"event_type": event_type}
            recovery_suggestions=[
                "Check event bus health"
                "Verify event format"
                "Check database connectivity"
                "Retry publishing"
            ]
            **kwargs
        )


class EventSubscribeError(BaseError):
    """Error subscribing to events"""

    def __init__(self, pattern: str, subscriber: str, reason: str, **kwargs) -> None:
        super().__init__(
            message=f"Failed to subscribe {subscriber} to pattern '{pattern}': {reason}"
            operation="subscribe_events"
            details={"pattern": pattern, "subscriber": subscriber}
            recovery_suggestions=[
                "Check subscription pattern format"
                "Verify subscriber callback"
                "Check event bus health"
                "Restart subscriber"
            ]
            **kwargs
        )


# Claude Integration Errors
class ClaudeError(BaseError):
    """Base class for Claude integration errors"""

    pass


class ClaudeRateLimitError(BaseError):
    """Error when Claude API rate limit is exceeded"""

    def __init__(self, wait_time: float, **kwargs) -> None:
        super().__init__(
            message=f"Claude API rate limit exceeded, wait {wait_time:.1f} seconds"
            operation="claude_api_call"
            details={"wait_time": wait_time}
            recovery_suggestions=[
                "Wait before retrying"
                "Implement exponential backoff"
                "Reduce API call frequency"
                "Check rate limit configuration"
            ]
            **kwargs
        )


class ClaudeServiceError(BaseError):
    """General Claude service error"""

    def __init__(self, operation: str, reason: str, **kwargs) -> None:
        super().__init__(
            message=f"Claude service error during {operation}: {reason}"
            operation=operation
            recovery_suggestions=[
                "Retry with exponential backoff"
                "Check Claude service health"
                "Verify API credentials"
                "Switch to backup service"
            ]
            **kwargs
        )
