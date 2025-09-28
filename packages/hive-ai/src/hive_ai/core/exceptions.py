"""
AI-specific exceptions that extend the Hive error hierarchy.

Provides rich context for AI operations while maintaining
consistency with the platform's error handling patterns.
"""

from typing import Optional, Dict, Any
from hive_errors import BaseError


class AIError(BaseError):
    """Base exception for all AI-related errors."""

    def __init__(
        self,
        message: str,
        model: Optional[str] = None,
        provider: Optional[str] = None,
        **kwargs
    ):
        super().__init__(message, component="hive-ai", **kwargs)
        self.model = model
        self.provider = provider


class ModelError(AIError):
    """Errors related to AI model operations."""

    def __init__(
        self,
        message: str,
        model: Optional[str] = None,
        provider: Optional[str] = None,
        request_id: Optional[str] = None,
        **kwargs
    ):
        super().__init__(message, model, provider, **kwargs)
        self.request_id = request_id


class VectorError(AIError):
    """Errors related to vector database operations."""

    def __init__(
        self,
        message: str,
        collection: Optional[str] = None,
        operation: Optional[str] = None,
        **kwargs
    ):
        super().__init__(message, **kwargs)
        self.collection = collection
        self.operation = operation


class PromptError(AIError):
    """Errors related to prompt template operations."""

    def __init__(
        self,
        message: str,
        template_name: Optional[str] = None,
        missing_variables: Optional[list] = None,
        **kwargs
    ):
        super().__init__(message, **kwargs)
        self.template_name = template_name
        self.missing_variables = missing_variables or []


class CostLimitError(AIError):
    """Error when cost limits are exceeded."""

    def __init__(
        self,
        message: str,
        current_cost: float,
        limit: float,
        period: str = "daily",
        **kwargs
    ):
        super().__init__(message, **kwargs)
        self.current_cost = current_cost
        self.limit = limit
        self.period = period


class ModelUnavailableError(ModelError):
    """Error when requested model is unavailable."""

    def __init__(
        self,
        message: str,
        model: str,
        provider: str,
        available_models: Optional[list] = None,
        **kwargs
    ):
        super().__init__(message, model, provider, **kwargs)
        self.available_models = available_models or []