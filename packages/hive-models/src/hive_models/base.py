"""
Base models and mixins for Hive platform data structures.

Provides foundational classes and mixins that other models can inherit from.
"""

from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel as PydanticBaseModel, Field, ConfigDict


class BaseModel(PydanticBaseModel):
    """
    Base model for all Hive platform data models.

    Provides common configuration and behavior for all models.
    """

    model_config = ConfigDict(
        # Use Enum values instead of names
        use_enum_values=True,
        # Validate on assignment
        validate_assignment=True,
        # Allow population by field name
        populate_by_name=True,
        # Include fields with None values in dict()
        # exclude_none=False,
        # Custom JSON encoder for datetime, UUID, etc.
        json_encoders={
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v),
        },
    )

    def dict(self, **kwargs) -> Dict[str, Any]:
        """Override dict() to ensure consistent serialization."""
        # Set defaults for common use cases
        kwargs.setdefault("exclude_none", True)
        kwargs.setdefault("exclude_unset", False)
        return super().model_dump(**kwargs)

    def json(self, **kwargs) -> str:
        """Override json() to ensure consistent JSON serialization."""
        kwargs.setdefault("exclude_none", True)
        kwargs.setdefault("indent", 2)
        return super().model_dump_json(**kwargs)


class TimestampMixin(BaseModel):
    """Mixin that adds timestamp fields to a model."""

    created_at: datetime = Field(default_factory=datetime.utcnow, description="Timestamp when the record was created")
    updated_at: Optional[datetime] = Field(default=None, description="Timestamp when the record was last updated")

    def update_timestamp(self) -> None:
        """Update the updated_at timestamp to current time."""
        self.updated_at = datetime.utcnow()


class IdentifiableMixin(BaseModel):
    """Mixin that adds a unique identifier to a model."""

    id: UUID = Field(default_factory=uuid4, description="Unique identifier for the record")

    def __hash__(self) -> int:
        """Make model hashable based on ID."""
        return hash(self.id)

    def __eq__(self, other: object) -> bool:
        """Compare models based on ID."""
        if not isinstance(other, IdentifiableMixin):
            return False
        return self.id == other.id


class StatusMixin(BaseModel):
    """Mixin that adds status tracking to a model."""

    status: str = Field(default="pending", description="Current status of the record")
    status_message: Optional[str] = Field(default=None, description="Additional information about the current status")
    status_updated_at: Optional[datetime] = Field(default=None, description="Timestamp when status was last changed")

    def update_status(self, status: str, message: Optional[str] = None) -> None:
        """
        Update the status with optional message.

        Args:
            status: New status value
            message: Optional status message
        """
        self.status = status
        self.status_message = message
        self.status_updated_at = datetime.utcnow()


class MetadataMixin(BaseModel):
    """Mixin that adds flexible metadata storage to a model."""

    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata as key-value pairs")
    tags: list[str] = Field(default_factory=list, description="Tags for categorization and filtering")

    def add_tag(self, tag: str) -> None:
        """Add a tag if it doesn't already exist."""
        if tag not in self.tags:
            self.tags.append(tag)

    def remove_tag(self, tag: str) -> None:
        """Remove a tag if it exists."""
        if tag in self.tags:
            self.tags.remove(tag)

    def has_tag(self, tag: str) -> bool:
        """Check if a tag exists."""
        return tag in self.tags

    def set_metadata(self, key: str, value: Any) -> None:
        """Set a metadata value."""
        self.metadata[key] = value

    def get_metadata(self, key: str, default: Any = None) -> Any:
        """Get a metadata value with optional default."""
        return self.metadata.get(key, default)
