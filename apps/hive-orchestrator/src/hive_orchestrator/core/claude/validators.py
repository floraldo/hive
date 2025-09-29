"""
Response validation utilities for Claude outputs
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Type

from hive_logging import get_logger
from pydantic import BaseModel, ValidationError

logger = get_logger(__name__)


class BaseResponseValidator(ABC):
    """Base class for response validators"""

    @abstractmethod
    def validate(self, data: Dict[str, Any]) -> Optional[BaseModel]:
        """Validate response data against a schema"""
        pass

    @abstractmethod
    def create_fallback(self, error_message: str, context: Dict[str, Any]) -> BaseModel:
        """Create a fallback response when validation fails"""
        pass


class PydanticValidator(BaseResponseValidator):
    """Validator using Pydantic models"""

    def __init__(self, model_class: Type[BaseModel]) -> None:
        """
        Initialize with a Pydantic model class

        Args:
            model_class: The Pydantic model to validate against
        """
        self.model_class = model_class

    def validate(self, data: Dict[str, Any]) -> Optional[BaseModel]:
        """
        Validate data against the Pydantic model

        Args:
            data: Dictionary to validate

        Returns:
            Validated model instance or None on failure
        """
        try:
            return self.model_class(**data)
        except ValidationError as e:
            logger.error(f"Validation failed: {e}")
            return None

    def create_fallback(self, error_message: str, context: Dict[str, Any]) -> BaseModel:
        """
        Create a fallback response with default values

        Args:
            error_message: Error that triggered the fallback
            context: Additional context for creating the fallback

        Returns:
            Fallback model instance with default values
        """
        # Create instance with minimal required fields
        # Use context to populate fields where possible
        try:
            # Try to create with default values from model schema
            defaults = {}
            for field_name, field in self.model_class.model_fields.items():
                if field_name in context:
                    defaults[field_name] = context[field_name]
                elif field.default is not None:
                    defaults[field_name] = field.default
                elif not field.is_required():
                    continue
                else:
                    # Provide sensible defaults for required fields
                    if field.annotation == str:
                        defaults[field_name] = ""
                    elif field.annotation == int:
                        defaults[field_name] = 0
                    elif field.annotation == bool:
                        defaults[field_name] = False
                    elif field.annotation == list:
                        defaults[field_name] = []
                    elif field.annotation == dict:
                        defaults[field_name] = {}
                    else:
                        defaults[field_name] = None

            return self.model_class(**defaults)
        except Exception as e:
            logger.error(f"Failed to create fallback: {e}")
            # Return minimal instance if fallback creation fails
            return self.model_class()


class ResponseValidator:
    """
    Main validation utility with fallback support
    """

    def __init__(self, validator: BaseResponseValidator) -> None:
        self.validator = validator

    def validate_response(
        self,
        data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
        use_fallback: bool = True,
    ) -> Optional[BaseModel]:
        """
        Validate response with optional fallback

        Args:
            data: Response data to validate
            context: Context for fallback creation
            use_fallback: Whether to create fallback on validation failure

        Returns:
            Validated model or fallback (if enabled) or None
        """
        # Try to validate the response
        validated = self.validator.validate(data)

        if validated:
            return validated

        # Create fallback if enabled
        if use_fallback and context:
            logger.info("Creating fallback response")
            return self.validator.create_fallback("Validation failed", context or {})

        return None
