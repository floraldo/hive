"""Advanced async error handling with monitoring integration."""

import asyncio
import functools
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable, Union, AsyncGenerator
from datetime import datetime, timedelta
from hive_logging import get_logger

from .base_exceptions import BaseError, AsyncTimeoutError, RetryExhaustedError
from .error_reporter import BaseErrorReporter

logger = get_logger(__name__)


@dataclass
class ErrorContext:
    """Context information for async error handling."""

    operation_name: str
    component: str
    start_time: datetime = field(default_factory=datetime.utcnow)
    timeout_duration: Optional[float] = None
    retry_attempt: int = 0
    max_retries: int = 0
    correlation_id: Optional[str] = None
    user_id: Optional[str] = None
    request_id: Optional[str] = None
    custom_context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ErrorStats:
    """Error statistics for monitoring."""

    total_errors: int = 0
    errors_by_type: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    errors_by_component: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    recent_errors: deque = field(default_factory=lambda: deque(maxlen=100))
    error_rate_per_minute: float = 0.0
    last_error_time: Optional[datetime] = None


class AsyncErrorHandler:
    """
    Advanced async error handler with monitoring and recovery.

    Features:
    - Context-aware error handling
    - Automatic retry with exponential backoff
    - Circuit breaker integration
    - Error rate monitoring
    - Recovery suggestions
    - Performance metrics integration
    """

    def __init__(
        self,
        error_reporter: Optional[BaseErrorReporter] = None,
        enable_monitoring: bool = True,
        max_error_history: int = 1000
    ):
        self.error_reporter = error_reporter
        self.enable_monitoring = enable_monitoring
        self.max_error_history = max_error_history

        # Error tracking
        self._error_stats = ErrorStats()
        self._error_history: deque = deque(maxlen=max_error_history)
        self._component_health: Dict[str, float] = defaultdict(lambda: 1.0)  # 0.0-1.0

        # Performance tracking
        self._operation_times: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
        self._success_rates: Dict[str, float] = defaultdict(lambda: 1.0)

    async def handle_error(
        self,
        error: Exception,
        context: ErrorContext,
        suppress: bool = False
    ) -> Optional[Exception]:
        """
        Handle an error with full context and monitoring.

        Args:
            error: The exception that occurred
            context: Error context information
            suppress: Whether to suppress the error (return None)

        Returns:
            The processed error or None if suppressed
        """
        # Record error occurrence
        error_record = await self._record_error(error, context)

        # Update statistics
        await self._update_error_stats(error, context)

        # Update component health
        await self._update_component_health(context.component, success=False)

        # Report error if reporter available
        if self.error_reporter:
            try:
                await self._report_error_async(error, context, error_record)
            except Exception as e:
                logger.error(f"Failed to report error: {e}")

        # Log error with context
        await self._log_error(error, context)

        # Return processed error
        if suppress:
            return None
        return error

    async def handle_success(self, context: ErrorContext, execution_time: float) -> None:
        """Record successful operation for health monitoring."""
        # Update component health
        await self._update_component_health(context.component, success=True)

        # Record operation timing
        self._operation_times[context.operation_name].append(execution_time)

        # Update success rates
        await self._update_success_rates(context.operation_name, success=True)

    async def _record_error(self, error: Exception, context: ErrorContext) -> Dict[str, Any]:
        """Record error details for analysis."""
        error_record = {
            "timestamp": datetime.utcnow(),
            "error_type": error.__class__.__name__,
            "error_message": str(error),
            "operation_name": context.operation_name,
            "component": context.component,
            "retry_attempt": context.retry_attempt,
            "max_retries": context.max_retries,
            "execution_time": (datetime.utcnow() - context.start_time).total_seconds(),
            "correlation_id": context.correlation_id,
            "timeout_duration": context.timeout_duration,
            "custom_context": context.custom_context,
        }

        # Add enhanced error details for BaseError instances
        if isinstance(error, BaseError):
            error_record.update({
                "error_details": error.details,
                "recovery_suggestions": error.recovery_suggestions,
                "original_error": str(error.original_error) if error.original_error else None,
            })

        self._error_history.append(error_record)
        return error_record

    async def _update_error_stats(self, error: Exception, context: ErrorContext) -> None:
        """Update error statistics."""
        self._error_stats.total_errors += 1
        self._error_stats.errors_by_type[error.__class__.__name__] += 1
        self._error_stats.errors_by_component[context.component] += 1
        self._error_stats.last_error_time = datetime.utcnow()

        # Calculate error rate per minute
        recent_errors = [
            e for e in self._error_history
            if (datetime.utcnow() - e["timestamp"]).total_seconds() <= 60
        ]
        self._error_stats.error_rate_per_minute = len(recent_errors)

    async def _update_component_health(self, component: str, success: bool) -> None:
        """Update component health score (exponential moving average)."""
        current_health = self._component_health[component]
        alpha = 0.1  # Smoothing factor

        if success:
            new_health = current_health + alpha * (1.0 - current_health)
        else:
            new_health = current_health + alpha * (0.0 - current_health)

        self._component_health[component] = max(0.0, min(1.0, new_health))

    async def _update_success_rates(self, operation: str, success: bool) -> None:
        """Update operation success rates."""
        current_rate = self._success_rates[operation]
        alpha = 0.1

        if success:
            new_rate = current_rate + alpha * (1.0 - current_rate)
        else:
            new_rate = current_rate + alpha * (0.0 - current_rate)

        self._success_rates[operation] = max(0.0, min(1.0, new_rate))

    async def _report_error_async(
        self,
        error: Exception,
        context: ErrorContext,
        error_record: Dict[str, Any]
    ) -> None:
        """Report error asynchronously if reporter supports it."""
        if hasattr(self.error_reporter, 'report_error_async'):
            await self.error_reporter.report_error_async(
                error,
                context=context.__dict__,
                additional_info=error_record
            )
        else:
            # Fallback to synchronous reporting
            self.error_reporter.report_error(
                error,
                context=context.__dict__,
                additional_info=error_record
            )

    async def _log_error(self, error: Exception, context: ErrorContext) -> None:
        """Log error with structured context."""
        log_data = {
            "operation": context.operation_name,
            "component": context.component,
            "error_type": error.__class__.__name__,
            "retry_attempt": context.retry_attempt,
            "correlation_id": context.correlation_id,
        }

        if context.retry_attempt > 0:
            logger.warning(
                f"Error in {context.operation_name} (attempt {context.retry_attempt}): {error}",
                extra=log_data
            )
        else:
            logger.error(
                f"Error in {context.operation_name}: {error}",
                extra=log_data
            )

    def get_error_statistics(self) -> Dict[str, Any]:
        """Get comprehensive error statistics."""
        return {
            "total_errors": self._error_stats.total_errors,
            "errors_by_type": dict(self._error_stats.errors_by_type),
            "errors_by_component": dict(self._error_stats.errors_by_component),
            "error_rate_per_minute": self._error_stats.error_rate_per_minute,
            "component_health": dict(self._component_health),
            "success_rates": dict(self._success_rates),
            "last_error_time": self._error_stats.last_error_time.isoformat() if self._error_stats.last_error_time else None,
        }

    def get_component_health(self, component: str) -> float:
        """Get health score for a specific component (0.0-1.0)."""
        return self._component_health[component]

    def get_operation_stats(self, operation: str) -> Dict[str, Any]:
        """Get statistics for a specific operation."""
        times = list(self._operation_times[operation])
        return {
            "success_rate": self._success_rates[operation],
            "total_calls": len(times),
            "avg_execution_time": sum(times) / len(times) if times else 0.0,
            "min_execution_time": min(times) if times else 0.0,
            "max_execution_time": max(times) if times else 0.0,
        }

    def get_recent_errors(self, component: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent errors, optionally filtered by component."""
        errors = list(self._error_history)

        if component:
            errors = [e for e in errors if e.get("component") == component]

        return errors[-limit:]

    async def predict_failure_risk(self, component: str, operation: str) -> Dict[str, Any]:
        """Predict failure risk based on recent patterns."""
        component_health = self.get_component_health(component)
        operation_stats = self.get_operation_stats(operation)

        # Calculate risk score (0.0-1.0)
        health_risk = 1.0 - component_health
        success_risk = 1.0 - operation_stats["success_rate"]

        # Recent error trend
        recent_errors = [
            e for e in self._error_history
            if e.get("component") == component and
               (datetime.utcnow() - e["timestamp"]).total_seconds() <= 300  # Last 5 minutes
        ]
        trend_risk = min(1.0, len(recent_errors) / 10)  # Max 10 errors = full risk

        # Combined risk score
        risk_score = (health_risk * 0.4 + success_risk * 0.4 + trend_risk * 0.2)

        return {
            "risk_score": risk_score,
            "risk_level": "high" if risk_score > 0.7 else "medium" if risk_score > 0.4 else "low",
            "component_health": component_health,
            "success_rate": operation_stats["success_rate"],
            "recent_error_count": len(recent_errors),
            "recommendations": self._get_risk_recommendations(risk_score, component, operation),
        }

    def _get_risk_recommendations(self, risk_score: float, component: str, operation: str) -> List[str]:
        """Generate risk mitigation recommendations."""
        recommendations = []

        if risk_score > 0.7:
            recommendations.extend([
                "Consider implementing circuit breaker for this component",
                "Increase monitoring and alerting",
                "Review error patterns and implement preventive measures",
            ])
        elif risk_score > 0.4:
            recommendations.extend([
                "Monitor component health closely",
                "Consider adding retry mechanisms",
                "Review recent error logs for patterns",
            ])

        # Component-specific recommendations
        component_health = self.get_component_health(component)
        if component_health < 0.8:
            recommendations.append(f"Component {component} showing degraded health - investigate root cause")

        return recommendations


# Context manager for automatic error handling
@asynccontextmanager
async def error_context(
    handler: AsyncErrorHandler,
    operation_name: str,
    component: str,
    timeout: Optional[float] = None,
    suppress_errors: bool = False,
    correlation_id: Optional[str] = None,
    **context_kwargs
) -> AsyncGenerator[ErrorContext, None]:
    """Context manager for automatic async error handling."""
    context = ErrorContext(
        operation_name=operation_name,
        component=component,
        timeout_duration=timeout,
        correlation_id=correlation_id,
        custom_context=context_kwargs
    )

    start_time = time.perf_counter()

    try:
        if timeout:
            async with asyncio.timeout(timeout):
                yield context
        else:
            yield context

        # Record success
        execution_time = time.perf_counter() - start_time
        await handler.handle_success(context, execution_time)

    except asyncio.TimeoutError as e:
        timeout_error = AsyncTimeoutError(
            message=f"Operation {operation_name} timed out after {timeout}s",
            component=component,
            operation=operation_name,
            timeout_duration=timeout,
            elapsed_time=time.perf_counter() - start_time
        )

        processed_error = await handler.handle_error(timeout_error, context, suppress_errors)
        if not suppress_errors and processed_error:
            raise processed_error from e

    except Exception as e:
        processed_error = await handler.handle_error(e, context, suppress_errors)
        if not suppress_errors and processed_error:
            raise processed_error


# Decorator for automatic async error handling
def handle_async_errors(
    handler: AsyncErrorHandler,
    component: str,
    operation_name: Optional[str] = None,
    timeout: Optional[float] = None,
    suppress_errors: bool = False,
    max_retries: int = 0,
    retry_delay: float = 1.0,
    exponential_backoff: bool = True
):
    """Decorator for automatic async error handling with retry logic."""

    def decorator(func: Callable) -> Callable:
        nonlocal operation_name
        if operation_name is None:
            operation_name = f"{func.__module__}.{func.__name__}"

        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            last_error = None

            for attempt in range(max_retries + 1):
                context = ErrorContext(
                    operation_name=operation_name,
                    component=component,
                    timeout_duration=timeout,
                    retry_attempt=attempt,
                    max_retries=max_retries
                )

                try:
                    async with error_context(
                        handler,
                        operation_name,
                        component,
                        timeout=timeout,
                        suppress_errors=False,
                        correlation_id=kwargs.get('correlation_id')
                    ):
                        return await func(*args, **kwargs)

                except Exception as e:
                    last_error = e

                    if attempt < max_retries:
                        # Calculate delay with optional exponential backoff
                        delay = retry_delay
                        if exponential_backoff:
                            delay *= (2 ** attempt)

                        logger.info(f"Retrying {operation_name} in {delay}s (attempt {attempt + 1}/{max_retries})")
                        await asyncio.sleep(delay)
                    else:
                        # All retries exhausted
                        retry_error = RetryExhaustedError(
                            message=f"All {max_retries} retry attempts failed for {operation_name}",
                            component=component,
                            operation=operation_name,
                            max_attempts=max_retries,
                            attempt_count=attempt + 1,
                            last_error=e
                        )

                        processed_error = await handler.handle_error(retry_error, context, suppress_errors)
                        if not suppress_errors and processed_error:
                            raise processed_error from e

            return None  # Should not reach here

        return wrapper
    return decorator


# Utility function for creating error contexts
def create_error_context(
    operation_name: str,
    component: str,
    correlation_id: Optional[str] = None,
    user_id: Optional[str] = None,
    request_id: Optional[str] = None,
    **custom_context
) -> ErrorContext:
    """Create an error context with common parameters."""
    return ErrorContext(
        operation_name=operation_name,
        component=component,
        correlation_id=correlation_id,
        user_id=user_id,
        request_id=request_id,
        custom_context=custom_context
    )