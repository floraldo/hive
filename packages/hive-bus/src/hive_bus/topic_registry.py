"""Topic registry for unified event routing.

During migration, both legacy and unified events can coexist.
This registry allows agents to:
- Subscribe to specific unified event types
- Route events to appropriate handlers
- Support pattern matching for event subscriptions

Architecture:
    - Topic-based routing (e.g., "task.*", "review.completed")
    - Backwards compatible with existing BaseEvent system
    - No breaking changes to existing agents

Usage:
    from hive_bus import TopicRegistry, UnifiedEventType

    # Create registry
    registry = TopicRegistry()

    # Register handler for task events
    registry.register("task.*", handle_task_events)

    # Register handler for specific event
    registry.register("review.completed", handle_review_completed)

    # Match event to handlers
    handlers = registry.get_handlers("task.created")
"""

import fnmatch
from collections import defaultdict
from collections.abc import Callable
from typing import Any

from hive_logging import get_logger

from .unified_events import UnifiedEventType

logger = get_logger(__name__)


class TopicRegistry:
    """Registry for topic-based event routing.

    Supports both exact topic matching and wildcard patterns:
    - "task.created" - exact match
    - "task.*" - all task events
    - "*.completed" - all completion events
    - "*" - all events
    """

    def __init__(self) -> None:
        """Initialize empty registry."""
        # Map topic patterns to handlers
        self._handlers: dict[str, list[Callable]] = defaultdict(list)

        # Pre-register all unified event types as topics
        self._initialize_unified_topics()

    def _initialize_unified_topics(self) -> None:
        """Initialize registry with all unified event type topics."""
        for event_type in UnifiedEventType:
            # Each event type is a valid topic
            logger.debug(f"Registered topic: {event_type.value}")

    def register(self, topic_pattern: str, handler: Callable[[Any], None]) -> None:
        """Register a handler for events matching the topic pattern.

        Args:
            topic_pattern: Topic pattern to match (supports wildcards)
            handler: Callable to invoke when event matches pattern

        Examples:
            registry.register("task.*", handle_all_tasks)
            registry.register("review.completed", handle_review_done)
            registry.register("*", handle_all_events)
        """
        if handler not in self._handlers[topic_pattern]:
            self._handlers[topic_pattern].append(handler)
            logger.info(f"Registered handler for topic pattern: {topic_pattern}")

    def unregister(self, topic_pattern: str, handler: Callable[[Any], None]) -> None:
        """Unregister a handler from a topic pattern.

        Args:
            topic_pattern: Topic pattern to unregister from
            handler: Handler to remove
        """
        if topic_pattern in self._handlers and handler in self._handlers[topic_pattern]:
            self._handlers[topic_pattern].remove(handler)
            logger.info(f"Unregistered handler from topic pattern: {topic_pattern}")

            # Clean up empty handler lists
            if not self._handlers[topic_pattern]:
                del self._handlers[topic_pattern]

    def get_handlers(self, topic: str) -> list[Callable]:
        """Get all handlers matching the given topic.

        Args:
            topic: Exact topic name to match against patterns

        Returns:
            List of handlers matching the topic

        Examples:
            # Topic: "task.created"
            # Matches patterns: "task.created", "task.*", "*"
            handlers = registry.get_handlers("task.created")
        """
        matched_handlers = []

        for pattern, handlers in self._handlers.items():
            if fnmatch.fnmatch(topic, pattern):
                matched_handlers.extend(handlers)

        return matched_handlers

    def get_handlers_for_event_type(self, event_type: UnifiedEventType) -> list[Callable]:
        """Get handlers for a specific unified event type.

        Args:
            event_type: UnifiedEventType enum value

        Returns:
            List of handlers matching the event type
        """
        return self.get_handlers(event_type.value)

    def list_patterns(self) -> list[str]:
        """List all registered topic patterns.

        Returns:
            List of topic patterns with registered handlers
        """
        return list(self._handlers.keys())

    def clear(self) -> None:
        """Clear all registered handlers."""
        self._handlers.clear()
        logger.info("Cleared all topic handlers")


# Global registry instance (optional - apps can create their own)
_global_registry = TopicRegistry()


def get_global_registry() -> TopicRegistry:
    """Get the global topic registry.

    This is a convenience function for simple use cases.
    For more complex scenarios, create dedicated registry instances.

    Returns:
        Global TopicRegistry instance
    """
    return _global_registry
