"""
Event subscription and handling for the Hive Event Bus

Provides both synchronous and asynchronous event subscribers
for flexible event handling patterns.
"""

import asyncio
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from hive_logging import get_logger

from .events import Event

logger = get_logger(__name__)


@dataclass
class EventSubscriber:
    """Synchronous event subscriber"""

    pattern: str
    callback: Callable[[Event], None]
    subscriber_name: str
    subscription_id: str = None
    created_at: datetime = None

    def __post_init__(self):
        if not self.subscription_id:
            self.subscription_id = str(uuid.uuid4())
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc)

    def handle_event(self, event: Event):
        """Handle an incoming event"""
        try:
            logger.debug(
                f"Subscriber {self.subscriber_name} handling event {event.event_id}"
            )
            self.callback(event)
        except Exception as e:
            logger.error(
                f"Subscriber {self.subscriber_name} failed to handle event {event.event_id}: {e}"
            )
            raise


@dataclass
class AsyncEventSubscriber:
    """Asynchronous event subscriber for future async support"""

    pattern: str
    callback: Callable[[Event], Any]  # Can return coroutine
    subscriber_name: str
    subscription_id: str = None
    created_at: datetime = None

    def __post_init__(self):
        if not self.subscription_id:
            self.subscription_id = str(uuid.uuid4())
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc)

    async def handle_event(self, event: Event):
        """Handle an incoming event asynchronously"""
        try:
            logger.debug(
                f"Async subscriber {self.subscriber_name} handling event {event.event_id}"
            )
            result = self.callback(event)

            # Handle both sync and async callbacks
            if asyncio.iscoroutine(result):
                await result

        except Exception as e:
            logger.error(
                f"Async subscriber {self.subscriber_name} failed to handle event {event.event_id}: {e}"
            )
            raise


class SubscriberRegistry:
    """Registry for managing event subscribers"""

    def __init__(self):
        self._subscribers = {}
        self._async_subscribers = {}

    def add_subscriber(self, subscriber: EventSubscriber):
        """Add a synchronous subscriber"""
        pattern = subscriber.pattern
        if pattern not in self._subscribers:
            self._subscribers[pattern] = []
        self._subscribers[pattern].append(subscriber)

    def add_async_subscriber(self, subscriber: AsyncEventSubscriber):
        """Add an asynchronous subscriber"""
        pattern = subscriber.pattern
        if pattern not in self._async_subscribers:
            self._async_subscribers[pattern] = []
        self._async_subscribers[pattern].append(subscriber)

    def remove_subscriber(self, subscription_id: str) -> bool:
        """Remove a subscriber by ID"""
        # Check sync subscribers
        for pattern, subscribers in self._subscribers.items():
            for i, subscriber in enumerate(subscribers):
                if subscriber.subscription_id == subscription_id:
                    del subscribers[i]
                    return True

        # Check async subscribers
        for pattern, subscribers in self._async_subscribers.items():
            for i, subscriber in enumerate(subscribers):
                if subscriber.subscription_id == subscription_id:
                    del subscribers[i]
                    return True

        return False

    def get_matching_subscribers(self, event_type: str):
        """Get all subscribers that match an event type"""
        matching = []

        for pattern, subscribers in self._subscribers.items():
            if self._matches_pattern(event_type, pattern):
                matching.extend(subscribers)

        return matching

    def get_matching_async_subscribers(self, event_type: str):
        """Get all async subscribers that match an event type"""
        matching = []

        for pattern, subscribers in self._async_subscribers.items():
            if self._matches_pattern(event_type, pattern):
                matching.extend(subscribers)

        return matching

    def _matches_pattern(self, event_type: str, pattern: str) -> bool:
        """Check if event type matches pattern"""
        if pattern == "*":
            return True
        if pattern == event_type:
            return True
        if pattern.endswith(".*"):
            prefix = pattern[:-2]
            return event_type.startswith(prefix + ".")
        return False


# Convenience functions for creating subscribers


def create_subscriber(
    pattern: str, callback: Callable[[Event], None], subscriber_name: str = "anonymous"
) -> EventSubscriber:
    """Create a synchronous event subscriber"""
    return EventSubscriber(
        pattern=pattern, callback=callback, subscriber_name=subscriber_name
    )


def create_async_subscriber(
    pattern: str, callback: Callable[[Event], Any], subscriber_name: str = "anonymous"
) -> AsyncEventSubscriber:
    """Create an asynchronous event subscriber"""
    return AsyncEventSubscriber(
        pattern=pattern, callback=callback, subscriber_name=subscriber_name
    )


# Decorator for easy subscription
def event_handler(pattern: str, subscriber_name: str = "anonymous"):
    """Decorator for creating event handlers"""

    def decorator(func):
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        # Attach subscription info to function
        wrapper._event_pattern = pattern
        wrapper._subscriber_name = subscriber_name
        wrapper._is_event_handler = True

        return wrapper

    return decorator
