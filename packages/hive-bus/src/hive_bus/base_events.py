from __future__ import annotations

from hive_logging import get_logger

logger = get_logger(__name__)

"""
Generic base event models.

These are pure, business-logic-free event patterns that can be used
to build any event-driven system.
"""

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass
class BaseEvent:
    """
    Generic base event for any event-driven system.

    Contains only the minimal, universal properties that any event needs:
    - Unique identifier
    - Timestamp
    - Event type
    - Source identifier
    - Payload data
    - Metadata
    """

    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    source: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    correlation_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert event to dictionary for serialization"""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "timestamp": self.timestamp.isoformat(),
            "source": self.source,
            "payload": self.payload,
            "metadata": self.metadata,
            "correlation_id": self.correlation_id
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BaseEvent:
        """Create event from dictionary"""
        timestamp = datetime.fromisoformat(data["timestamp"])

        return cls(
            event_id=data["event_id"],
            event_type=data["event_type"],
            timestamp=timestamp,
            source=data["source"],
            payload=data.get("payload", {}),
            metadata=data.get("metadata", {}),
            correlation_id=data.get("correlation_id")
        )
