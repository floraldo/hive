from hive_logging import get_logger

logger = get_logger(__name__)

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

# Topic-based event routing
from .topic_registry import TopicRegistry, get_global_registry

# Unified event types for cross-agent coordination
from .unified_events import (
    UnifiedEvent,
    UnifiedEventType,
    create_deployment_event,
    create_task_event,
    create_workflow_event,
)

__all__ = [
    "BaseBus",
    "BaseEvent",
    "BaseSubscriber",
    # Unified events
    "UnifiedEvent",
    "UnifiedEventType",
    "create_task_event",
    "create_workflow_event",
    "create_deployment_event",
    # Topic registry
    "TopicRegistry",
    "get_global_registry",
]
