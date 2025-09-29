from hive_logging import get_logger

logger = get_logger(__name__)

"""
Generic event bus base class.

Provides reusable pub/sub patterns that can be extended
for any event-driven system.
"""

import threading
from abc import ABC, abstractmethod
from collections.abc import Callable

from .base_events import BaseEvent
from .subscribers import BaseSubscriber


class BaseBus(ABC):
    """
    Generic base event bus.

    Provides the fundamental pub/sub patterns that any event bus needs:
    - Subscription management
    - Event routing
    - Pattern matching

    Subclasses must implement storage and notification mechanisms.
    """

    def __init__(self) -> None:
        """Initialize the base bus"""
        self._subscribers: dict[str, list[BaseSubscriber]] = {}
        self._subscriber_lock = threading.Lock()

    @abstractmethod
    def publish(self, event: BaseEvent, **kwargs) -> str:
        """
        Publish an event to the bus.

        Args:
            event: Event to publish
            **kwargs: Implementation-specific options

        Returns:
            Event ID or publication reference
        """
        pass

    def subscribe(
        self,
        event_pattern: str,
        callback: Callable[[BaseEvent], None],
        subscriber_name: str = "anonymous",
    ) -> str:
        """
        Subscribe to events matching a pattern.

        Args:
            event_pattern: Event type pattern (supports wildcards),
            callback: Function to call when event matches,
            subscriber_name: Name of the subscribing entity

        Returns:
            Subscription ID
        """
        subscriber = BaseSubscriber(pattern=event_pattern, callback=callback, subscriber_name=subscriber_name)

        with self._subscriber_lock:
            if event_pattern not in self._subscribers:
                self._subscribers[event_pattern] = []
            self._subscribers[event_pattern].append(subscriber)

        return subscriber.subscription_id

    def unsubscribe(self, subscription_id: str) -> bool:
        """
        Remove a subscription.

        Args:
            subscription_id: ID of subscription to remove

        Returns:
            True if subscription was found and removed
        """
        with self._subscriber_lock:
            for pattern, subscribers in self._subscribers.items():
                for i, subscriber in enumerate(subscribers):
                    if subscriber.subscription_id == subscription_id:
                        del subscribers[i]
                        return True
        return False

    def _notify_subscribers(self, event: BaseEvent) -> None:
        """Notify all matching subscribers of an event"""
        with self._subscriber_lock:
            for pattern, subscribers in self._subscribers.items():
                if self._event_matches_pattern(event.event_type, pattern):
                    for subscriber in subscribers:
                        try:
                            subscriber.handle_event(event)
                        except Exception:
                            # Subclasses can override error handling
                            self._handle_subscriber_error(subscriber, event)

    def _event_matches_pattern(self, event_type: str, pattern: str) -> bool:
        """Check if event type matches subscription pattern"""
        if pattern == "*":
            return True
        if pattern == event_type:
            return True
        if pattern.endswith(".*") and event_type.startswith(pattern[:-2]):
            return True
        return False

    def _handle_subscriber_error(self, subscriber: BaseSubscriber, event: BaseEvent) -> None:
        """Handle subscriber callback errors. Override in subclasses."""
        pass
