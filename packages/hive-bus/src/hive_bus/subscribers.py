from hive_logging import get_logger

logger = get_logger(__name__)

"""
Generic subscription management.

Provides reusable patterns for managing event subscribers
in any event-driven system.
"""

import uuid
from collections.abc import Callable
from dataclasses import dataclass

from .base_events import BaseEvent


@dataclass
class BaseSubscriber:
    """
    Generic event subscriber.

    Contains only the minimal, universal properties needed
    for subscription management in any system.
    """

    subscription_id: str
    pattern: str
    callback: Callable[[BaseEvent], None]
    subscriber_name: str = "anonymous"

    def __init__(
        self,
        pattern: str,
        callback: Callable[[BaseEvent], None],
        subscriber_name: str = "anonymous",
    ):
        self.subscription_id = str(uuid.uuid4())
        self.pattern = pattern
        self.callback = callback
        self.subscriber_name = subscriber_name

    def handle_event(self, event: BaseEvent) -> None:
        """Handle an event by calling the callback"""
        try:
            self.callback(event)
        except Exception as e:
            # Let the calling system decide how to handle callback errors
            raise e
