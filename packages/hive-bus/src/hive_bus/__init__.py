"""
Generic messaging and event bus toolkit.

Provides reusable components for building event-driven systems:
- Generic event models
- Basic pub/sub patterns
- Message routing utilities
- Subscription management

This package contains NO business logic - it's a generic toolkit
that can be used to build any event-driven system.
"""

from .base_bus import BaseBus
from .base_events import BaseEvent
from .subscribers import BaseSubscriber

__all__ = ["BaseEvent", "BaseBus", "BaseSubscriber"]
