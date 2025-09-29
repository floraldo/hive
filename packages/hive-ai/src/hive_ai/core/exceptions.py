from __future__ import annotations

from hive_logging import get_logger

logger = get_logger(__name__)

"""
AI-specific exceptions that extend the Hive error hierarchy.

Provides rich context for AI operations while maintaining
consistency with the platform's error handling patterns.
"""


from hive_errors import BaseError


class AIError(BaseError):
    """Base exception for all AI-related errors.

    Provides common attributes for all AI-specific exceptions including
    model and provider context for better error tracking and debugging.
    """

    def __init__(
        self,
        message: str,
        model: str | None = None,
        provider: str | None = None,
        **kwargs,
    ) -> None:
        """Initialize AI error with model and provider context.

        Args:
            message: Human-readable error description.,
            model: Name of the model that caused the error.,
            provider: Name of the AI provider (anthropic, openai, etc.).
            **kwargs: Additional context passed to BaseError.
        """
        super().__init__(message, component="hive-ai", **kwargs)
        self.model = model
        self.provider = provider


class ModelError(BaseError):
    """Errors related to AI model operations.

    Specialized error for model-specific issues like API failures
    invalid responses, or rate limiting.
    """

    def __init__(
        self,
        message: str,
        model: str | None = None,
        provider: str | None = None,
        request_id: str | None = None,
        **kwargs,
    ) -> None:
        """Initialize model error with request tracking.

        Args:
            message: Human-readable error description.,
            model: Name of the model that failed.,
            provider: Name of the AI provider.,
            request_id: Unique identifier for the failed request.
            **kwargs: Additional context passed to BaseError.
        """
        super().__init__(message, model, provider, **kwargs)
        self.request_id = request_id


class VectorError(BaseError):
    """Errors related to vector database operations.

    Covers vector storage, retrieval, and similarity search failures.
    """

    def __init__(
        self,
        message: str,
        collection: str | None = None,
        operation: str | None = None,
        **kwargs,
    ) -> None:
        """Initialize vector error with operation context.

        Args:
            message: Human-readable error description.,
            collection: Name of the vector collection involved.,
            operation: Type of vector operation that failed.
            **kwargs: Additional context passed to BaseError.
        """
        super().__init__(message, **kwargs)
        self.collection = collection
        self.operation = operation


class PromptError(BaseError):
    """Errors related to prompt template operations.

    Handles template validation, variable substitution, and rendering failures.
    """

    def __init__(
        self,
        message: str,
        template_name: str | None = None,
        missing_variables: list | None = None,
        **kwargs,
    ) -> None:
        """Initialize prompt error with template context.

        Args:
            message: Human-readable error description.,
            template_name: Name of the template that failed.,
            missing_variables: List of required variables that were missing.
            **kwargs: Additional context passed to BaseError.
        """
        super().__init__(message, **kwargs)
        self.template_name = template_name
        self.missing_variables = missing_variables or []


class CostLimitError(BaseError):
    """Error when cost limits are exceeded.

    Prevents runaway AI costs by enforcing daily/monthly spending limits.
    """

    def __init__(
        self,
        message: str,
        current_cost: float,
        limit: float,
        period: str = "daily",
        **kwargs,
    ) -> None:
        """Initialize cost limit error with spending details.

        Args:
            message: Human-readable error description.,
            current_cost: Current spending amount in USD.,
            limit: The spending limit that was exceeded.,
            period: Time period for the limit (daily, monthly).
            **kwargs: Additional context passed to BaseError.
        """
        super().__init__(message, **kwargs)
        self.current_cost = current_cost
        self.limit = limit
        self.period = period


class ModelUnavailableError(BaseError):
    """Error when requested model is unavailable.

    Indicates the requested model is not configured or not accessible
    with suggestions for available alternatives.
    """

    def __init__(
        self,
        message: str,
        model: str,
        provider: str,
        available_models: list | None = None,
        **kwargs,
    ) -> None:
        """Initialize model unavailable error with alternatives.

        Args:
            message: Human-readable error description.,
            model: Name of the unavailable model.,
            provider: Name of the AI provider.,
            available_models: List of available model alternatives.
            **kwargs: Additional context passed to BaseError.
        """
        super().__init__(message, model, provider, **kwargs)
        self.available_models = available_models or []
