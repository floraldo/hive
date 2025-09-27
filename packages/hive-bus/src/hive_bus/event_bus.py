"""
Core Event Bus implementation for Hive

Provides a database-backed event bus for reliable inter-agent communication.
The bus makes the implicit choreography pattern explicit and adds full
event history for debugging and replay capabilities.
"""

import json
import sqlite3
import logging
import threading
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Callable, Union
from contextlib import contextmanager

from hive_core_db.connection_pool import get_pooled_connection
from hive_db_utils.config import get_config
from hive_errors import EventBusError, EventPublishError, EventSubscribeError

from .events import Event, TaskEvent, AgentEvent, WorkflowEvent
from .subscribers import EventSubscriber

logger = logging.getLogger(__name__)


class EventBus:
    """
    Database-backed event bus for inter-agent communication

    Features:
    - Persistent event storage in SQLite
    - Topic-based subscription
    - Event history and replay
    - Correlation tracking
    - Async-ready architecture
    """

    def __init__(self):
        """Initialize the event bus"""
        self.config = get_config()
        self._subscribers: Dict[str, List[EventSubscriber]] = {}
        self._subscriber_lock = threading.Lock()
        self._ensure_event_tables()

    def _ensure_event_tables(self):
        """Ensure event storage tables exist"""
        with get_pooled_connection() as conn:
            cursor = conn.cursor()

            # Events table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    event_id TEXT PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    source_agent TEXT NOT NULL,
                    correlation_id TEXT,
                    payload TEXT NOT NULL,
                    metadata TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Event subscriptions table (for persistent subscriptions)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS event_subscriptions (
                    subscription_id TEXT PRIMARY KEY,
                    event_pattern TEXT NOT NULL,
                    subscriber_agent TEXT NOT NULL,
                    callback_info TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    active INTEGER DEFAULT 1
                )
            """)

            # Indexes for performance
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_events_type_timestamp
                ON events(event_type, timestamp)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_events_correlation
                ON events(correlation_id)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_events_source_agent
                ON events(source_agent)
            """)

            conn.commit()

    def publish(
        self,
        event: Union[Event, Dict[str, Any]],
        correlation_id: Optional[str] = None
    ) -> str:
        """
        Publish an event to the bus

        Args:
            event: Event object or event data dict
            correlation_id: Optional correlation ID for tracking

        Returns:
            Event ID of the published event

        Raises:
            EventPublishError: If publishing fails
        """
        try:
            # Convert dict to Event if needed
            if isinstance(event, dict):
                event = Event.from_dict(event)

            # Set correlation ID if provided
            if correlation_id:
                event.correlation_id = correlation_id

            # Store in database
            with get_pooled_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO events (
                        event_id, event_type, timestamp, source_agent,
                        correlation_id, payload, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    event.event_id,
                    event.event_type,
                    event.timestamp.isoformat(),
                    event.source_agent,
                    event.correlation_id,
                    json.dumps(event.payload),
                    json.dumps(event.metadata)
                ))
                conn.commit()

            # Notify subscribers
            self._notify_subscribers(event)

            logger.debug(f"Published event {event.event_id} of type {event.event_type}")
            return event.event_id

        except Exception as e:
            raise EventPublishError(f"Failed to publish event: {e}") from e

    def subscribe(
        self,
        event_pattern: str,
        callback: Callable[[Event], None],
        subscriber_name: str = "anonymous"
    ) -> str:
        """
        Subscribe to events matching a pattern

        Args:
            event_pattern: Event type pattern (supports wildcards)
            callback: Function to call when event matches
            subscriber_name: Name of the subscribing agent

        Returns:
            Subscription ID
        """
        try:
            subscriber = EventSubscriber(
                pattern=event_pattern,
                callback=callback,
                subscriber_name=subscriber_name
            )

            with self._subscriber_lock:
                if event_pattern not in self._subscribers:
                    self._subscribers[event_pattern] = []
                self._subscribers[event_pattern].append(subscriber)

            logger.debug(f"Added subscription for {event_pattern} by {subscriber_name}")
            return subscriber.subscription_id

        except Exception as e:
            raise EventSubscribeError(f"Failed to subscribe: {e}") from e

    def unsubscribe(self, subscription_id: str) -> bool:
        """
        Remove a subscription

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
                        logger.debug(f"Removed subscription {subscription_id}")
                        return True
        return False

    def _notify_subscribers(self, event: Event):
        """Notify all matching subscribers of an event"""
        with self._subscriber_lock:
            for pattern, subscribers in self._subscribers.items():
                if self._event_matches_pattern(event.event_type, pattern):
                    for subscriber in subscribers:
                        try:
                            subscriber.handle_event(event)
                        except Exception as e:
                            logger.error(f"Subscriber {subscriber.subscriber_name} failed: {e}")

    def _event_matches_pattern(self, event_type: str, pattern: str) -> bool:
        """Check if event type matches subscription pattern"""
        if pattern == "*":
            return True
        if pattern == event_type:
            return True
        if pattern.endswith(".*") and event_type.startswith(pattern[:-2]):
            return True
        return False

    def get_events(
        self,
        event_type: Optional[str] = None,
        correlation_id: Optional[str] = None,
        source_agent: Optional[str] = None,
        since: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Event]:
        """
        Query events from the bus

        Args:
            event_type: Filter by event type
            correlation_id: Filter by correlation ID
            source_agent: Filter by source agent
            since: Only events after this timestamp
            limit: Maximum number of events to return

        Returns:
            List of matching events
        """
        query_parts = ["SELECT * FROM events WHERE 1=1"]
        params = []

        if event_type:
            query_parts.append("AND event_type = ?")
            params.append(event_type)

        if correlation_id:
            query_parts.append("AND correlation_id = ?")
            params.append(correlation_id)

        if source_agent:
            query_parts.append("AND source_agent = ?")
            params.append(source_agent)

        if since:
            query_parts.append("AND timestamp >= ?")
            params.append(since.isoformat())

        query_parts.append("ORDER BY timestamp DESC LIMIT ?")
        params.append(limit)

        query = " ".join(query_parts)

        with get_pooled_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()

        events = []
        for row in rows:
            event_data = {
                "event_id": row[0],
                "event_type": row[1],
                "timestamp": row[2],
                "source_agent": row[3],
                "correlation_id": row[4],
                "payload": json.loads(row[5]) if row[5] else {},
                "metadata": json.loads(row[6]) if row[6] else {},
            }
            events.append(Event.from_dict(event_data))

        return events

    def get_event_history(
        self,
        correlation_id: str,
        limit: int = 50
    ) -> List[Event]:
        """Get all events for a correlation ID (workflow trace)"""
        return self.get_events(correlation_id=correlation_id, limit=limit)

    def clear_old_events(self, days_to_keep: int = 30):
        """Clean up old events to prevent database growth"""
        cutoff_date = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        cutoff_date = cutoff_date.replace(day=cutoff_date.day - days_to_keep)

        with get_pooled_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM events WHERE timestamp < ?",
                (cutoff_date.isoformat(),)
            )
            deleted_count = cursor.rowcount
            conn.commit()

        logger.info(f"Cleaned up {deleted_count} old events")
        return deleted_count


# Global event bus instance
_event_bus: Optional[EventBus] = None
_bus_lock = threading.Lock()


def get_event_bus() -> EventBus:
    """Get or create the global event bus instance"""
    global _event_bus

    if _event_bus is None:
        with _bus_lock:
            if _event_bus is None:
                _event_bus = EventBus()
                logger.info("Event bus initialized")

    return _event_bus


def reset_event_bus():
    """Reset the global event bus (for testing)"""
    global _event_bus
    _event_bus = None