"""
Unit tests for base_exceptions module.

Tests all custom exception classes to ensure they:
- Can be raised with required and optional parameters
- Store all custom attributes correctly
- Serialize to dictionaries correctly
- Inherit from BaseError properly
"""

from __future__ import annotations

import pytest

from hive_errors.base_exceptions import (
    AsyncTimeoutError,
    BaseError,
    CircuitBreakerOpenError,
    ConfigurationError,
    ConnectionError,
    PoolExhaustedError,
    ResourceError,
    RetryExhaustedError,
    TimeoutError,
    ValidationError,
)


class TestBaseError:
    """Test the generic BaseError class."""

    def test_base_error_minimal(self):
        """Test BaseError with minimal parameters."""
        error = BaseError("Test error")
        assert error.message == "Test error"
        assert error.component == "unknown"
        assert error.operation is None
        assert error.details == {}
        assert error.recovery_suggestions == []
        assert error.original_error is None

    def test_base_error_full_parameters(self):
        """Test BaseError with all parameters."""
        original = ValueError("Original error"),
        error = BaseError(
            message="Test error",
            component="test_component",
            operation="test_operation",
            details={"key": "value"},
            recovery_suggestions=["Retry", "Check config"],
            original_error=original,
        )

        assert error.message == "Test error"
        assert error.component == "test_component"
        assert error.operation == "test_operation"
        assert error.details == {"key": "value"}
        assert error.recovery_suggestions == ["Retry", "Check config"]
        assert error.original_error is original

    def test_base_error_to_dict(self):
        """Test BaseError serialization to dictionary."""
        original = ValueError("Original error"),
        error = BaseError(
            message="Test error",
            component="test_component",
            operation="test_operation",
            details={"key": "value"},
            recovery_suggestions=["Retry"],
            original_error=original,
        )

        error_dict = error.to_dict()

        assert error_dict["error_type"] == "BaseError"
        assert error_dict["message"] == "Test error"
        assert error_dict["component"] == "test_component"
        assert error_dict["operation"] == "test_operation"
        assert error_dict["details"] == {"key": "value"}
        assert error_dict["recovery_suggestions"] == ["Retry"]
        assert error_dict["original_error"] == "Original error"

    def test_base_error_to_dict_no_original(self):
        """Test BaseError serialization without original error."""
        error = BaseError("Test error"),
        error_dict = error.to_dict()

        assert error_dict["original_error"] is None

    def test_base_error_can_be_raised(self):
        """Test that BaseError can be raised and caught."""
        with pytest.raises(BaseError) as exc_info:
            raise BaseError("Test error", component="test")

        assert exc_info.value.message == "Test error"
        assert exc_info.value.component == "test"


class TestDerivedErrors:
    """Test derived error classes inherit correctly."""

    def test_configuration_error(self):
        """Test ConfigurationError inherits from BaseError."""
        error = ConfigurationError("Config error", component="config")
        assert isinstance(error, BaseError)
        assert error.message == "Config error"
        assert error.component == "config"

    def test_connection_error(self):
        """Test ConnectionError inherits from BaseError."""
        error = ConnectionError("Connection failed", component="database")
        assert isinstance(error, BaseError)
        assert error.message == "Connection failed"

    def test_validation_error(self):
        """Test ValidationError inherits from BaseError."""
        error = ValidationError("Invalid data", component="validator")
        assert isinstance(error, BaseError)
        assert error.message == "Invalid data"

    def test_timeout_error(self):
        """Test TimeoutError inherits from BaseError."""
        error = TimeoutError("Operation timed out", component="api")
        assert isinstance(error, BaseError)
        assert error.message == "Operation timed out"

    def test_resource_error(self):
        """Test ResourceError inherits from BaseError."""
        error = ResourceError("Out of memory", component="memory")
        assert isinstance(error, BaseError)
        assert error.message == "Out of memory"


class TestCircuitBreakerOpenError:
    """Test CircuitBreakerOpenError with custom attributes."""

    def test_circuit_breaker_error_defaults(self):
        """Test CircuitBreakerOpenError with default values."""
        error = CircuitBreakerOpenError()
        assert error.message == "Circuit breaker is open - operation blocked"
        assert error.component == "circuit_breaker"
        assert error.failure_count is None
        assert error.recovery_time is None

    def test_circuit_breaker_error_custom_values(self):
        """Test CircuitBreakerOpenError with custom values."""
        error = CircuitBreakerOpenError(
            message="Custom message",
            component="custom_component",
            operation="test_op",
            failure_count=5,
            recovery_time=30.0,
        )

        assert error.message == "Custom message"
        assert error.component == "custom_component"
        assert error.operation == "test_op"
        assert error.failure_count == 5
        assert error.recovery_time == 30.0

    def test_circuit_breaker_error_to_dict(self):
        """Test CircuitBreakerOpenError serialization includes custom fields."""
        error = CircuitBreakerOpenError(
            failure_count=5,
            recovery_time=30.0,
        )

        error_dict = error.to_dict()

        assert error_dict["error_type"] == "CircuitBreakerOpenError"
        assert error_dict["failure_count"] == 5
        assert error_dict["recovery_time"] == 30.0


class TestAsyncTimeoutError:
    """Test AsyncTimeoutError with timeout-specific attributes."""

    def test_async_timeout_error_defaults(self):
        """Test AsyncTimeoutError with default values."""
        error = AsyncTimeoutError()
        assert error.message == "Async operation timed out"
        assert error.component == "async_timeout"
        assert error.timeout_duration is None
        assert error.elapsed_time is None

    def test_async_timeout_error_custom_values(self):
        """Test AsyncTimeoutError with custom values."""
        error = AsyncTimeoutError(
            message="Operation exceeded timeout",
            component="api",
            operation="fetch_data",
            timeout_duration=5.0,
            elapsed_time=7.5,
        )

        assert error.message == "Operation exceeded timeout"
        assert error.component == "api"
        assert error.operation == "fetch_data"
        assert error.timeout_duration == 5.0
        assert error.elapsed_time == 7.5

    def test_async_timeout_error_to_dict(self):
        """Test AsyncTimeoutError serialization includes timeout fields."""
        error = AsyncTimeoutError(
            timeout_duration=5.0,
            elapsed_time=7.5,
        )

        error_dict = error.to_dict()

        assert error_dict["error_type"] == "AsyncTimeoutError"
        assert error_dict["timeout_duration"] == 5.0
        assert error_dict["elapsed_time"] == 7.5


class TestRetryExhaustedError:
    """Test RetryExhaustedError with retry-specific attributes."""

    def test_retry_exhausted_error_defaults(self):
        """Test RetryExhaustedError with default values."""
        error = RetryExhaustedError()
        assert error.message == "All retry attempts exhausted"
        assert error.component == "retry_mechanism"
        assert error.max_attempts is None
        assert error.attempt_count is None
        assert error.last_error is None

    def test_retry_exhausted_error_custom_values(self):
        """Test RetryExhaustedError with custom values."""
        last_error = ValueError("Connection failed"),
        error = RetryExhaustedError(
            message="Retries exhausted after 3 attempts",
            component="api_client",
            operation="fetch",
            max_attempts=3,
            attempt_count=3,
            last_error=last_error,
        )

        assert error.message == "Retries exhausted after 3 attempts"
        assert error.component == "api_client"
        assert error.operation == "fetch"
        assert error.max_attempts == 3
        assert error.attempt_count == 3
        assert error.last_error is last_error
        assert error.original_error is last_error  # Should be set via parent

    def test_retry_exhausted_error_to_dict(self):
        """Test RetryExhaustedError serialization includes retry fields."""
        last_error = ValueError("Connection failed"),
        error = RetryExhaustedError(
            max_attempts=3,
            attempt_count=3,
            last_error=last_error,
        )

        error_dict = error.to_dict()

        assert error_dict["error_type"] == "RetryExhaustedError"
        assert error_dict["max_attempts"] == 3
        assert error_dict["attempt_count"] == 3
        assert error_dict["last_error"] == "Connection failed"


class TestPoolExhaustedError:
    """Test PoolExhaustedError with pool-specific attributes."""

    def test_pool_exhausted_error_defaults(self):
        """Test PoolExhaustedError with default values."""
        error = PoolExhaustedError()
        assert error.message == "Resource pool exhausted"
        assert error.component == "connection_pool"
        assert error.pool_size is None
        assert error.active_connections is None

    def test_pool_exhausted_error_custom_values(self):
        """Test PoolExhaustedError with custom values."""
        error = PoolExhaustedError(
            message="All connections in use",
            component="database_pool",
            operation="acquire",
            pool_size=10,
            active_connections=10,
        )

        assert error.message == "All connections in use"
        assert error.component == "database_pool"
        assert error.operation == "acquire"
        assert error.pool_size == 10
        assert error.active_connections == 10

    def test_pool_exhausted_error_to_dict(self):
        """Test PoolExhaustedError serialization includes pool fields."""
        error = PoolExhaustedError(
            pool_size=10,
            active_connections=10,
        )

        error_dict = error.to_dict()

        assert error_dict["error_type"] == "PoolExhaustedError"
        assert error_dict["pool_size"] == 10
        assert error_dict["active_connections"] == 10


class TestErrorInheritance:
    """Test that all errors can be caught as BaseError."""

    @pytest.mark.parametrize(
        "error_class",
        [
            ConfigurationError,
            ConnectionError,
            ValidationError,
            TimeoutError,
            ResourceError,
            CircuitBreakerOpenError,
            AsyncTimeoutError,
            RetryExhaustedError,
            PoolExhaustedError,
        ],
    )
    def test_all_errors_are_base_errors(self, error_class):
        """Test that all custom errors can be caught as BaseError."""
        with pytest.raises(BaseError):
            raise error_class("Test error")

    @pytest.mark.parametrize(
        "error_class",
        [
            ConfigurationError,
            ConnectionError,
            ValidationError,
            TimeoutError,
            ResourceError,
            CircuitBreakerOpenError,
            AsyncTimeoutError,
            RetryExhaustedError,
            PoolExhaustedError,
        ],
    )
    def test_all_errors_have_to_dict(self, error_class):
        """Test that all custom errors have to_dict() method."""
        error = error_class("Test error"),
        error_dict = error.to_dict()

        assert isinstance(error_dict, dict)
        assert "error_type" in error_dict
        assert "message" in error_dict
        assert error_dict["message"] == "Test error"
