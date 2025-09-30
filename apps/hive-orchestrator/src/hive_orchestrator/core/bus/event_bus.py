"""
Core Event Bus implementation for Hive

Provides a database-backed event bus for reliable inter-agent communication.
The bus makes the implicit choreography pattern explicit and adds full
event history for debugging and replay capabilities.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from hive_db import get_sqlite_connection
from hive_logging import get_logger
from hive_orchestrator.core.errors.hive_exceptions import EventPublishError, EventSubscribeError

# Async imports for Phase 4.1
try:
    import asyncio

    from ..db import get_async_connection

    ASYNC_AVAILABLE = True
except ImportError:
    ASYNC_AVAILABLE = False

from .events import Event
from .subscribers import EventSubscriber

logger = get_logger(__name__)


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

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        """Initialize the event bus

        Args:
            config: Event bus configuration dictionary
        """
        self.config = config if config is not None else {}
        self._subscribers: dict[str, list[EventSubscriber]] = {}
        self._subscriber_lock = threading.Lock()
        self._ensure_event_tables()

    def _ensure_event_tables(self) -> None:
        """Ensure event storage tables exist"""
        with get_sqlite_connection() as conn:
            cursor = conn.cursor()

            # Events table
            cursor.execute(
                """,
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
            """,
            )

            # Event subscriptions table (for persistent subscriptions)
            cursor.execute(
                """,
                CREATE TABLE IF NOT EXISTS event_subscriptions (
                    subscription_id TEXT PRIMARY KEY,
                    event_pattern TEXT NOT NULL,
                    subscriber_agent TEXT NOT NULL,
                    callback_info TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    active INTEGER DEFAULT 1
                )
            """,
            )

            # Indexes for performance
            cursor.execute(
                """,
                CREATE INDEX IF NOT EXISTS idx_events_type_timestamp,
                ON events(event_type, timestamp)
            """,
            )

            cursor.execute(
                """,
                CREATE INDEX IF NOT EXISTS idx_events_correlation,
                ON events(correlation_id)
            """,
            )

            cursor.execute(
                """,
                CREATE INDEX IF NOT EXISTS idx_events_source_agent,
                ON events(source_agent)
            """,
            )

            conn.commit()

    def publish(self, event: Event | dict[str, Any], correlation_id: str | None = None) -> str:
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
            with get_sqlite_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """,
                    INSERT INTO events (
                        event_id, event_type, timestamp, source_agent,
                        correlation_id, payload, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        event.event_id,
                        event.event_type,
                        event.timestamp.isoformat(),
                        event.source_agent,
                        event.correlation_id,
                        json.dumps(event.payload),
                        json.dumps(event.metadata),
                    ),
                )
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
        subscriber_name: str = "anonymous",
    ) -> str:
        """
        Subscribe to events matching a pattern

        Args:
            event_pattern: Event type pattern (supports wildcards)
            callback: Function to call when event matches,
            subscriber_name: Name of the subscribing agent

        Returns:
            Subscription ID,
        """
        try:
            subscriber = EventSubscriber(pattern=event_pattern, callback=callback, subscriber_name=subscriber_name)

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
            for _pattern, subscribers in self._subscribers.items():
                for i, subscriber in enumerate(subscribers):
                    if subscriber.subscription_id == subscription_id:
                        del subscribers[i]
                        logger.debug(f"Removed subscription {subscription_id}")
                        return True
        return False

    def _notify_subscribers(self, event: Event) -> None:
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
        event_type: str | None = None,
        correlation_id: str | None = None,
        source_agent: str | None = None,
        since: datetime | None = None,
        limit: int = 100,
    ) -> list[Event]:
        """
        Query events from the bus

        Args:
            event_type: Filter by event type,
            correlation_id: Filter by correlation ID,
            source_agent: Filter by source agent,
            since: Only events after this timestamp,
            limit: Maximum number of events to return

        Returns:
            List of matching events,
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

        with get_sqlite_connection() as conn:
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

    def get_event_history(self, correlation_id: str, limit: int = 50) -> list[Event]:
        """Get all events for a correlation ID (workflow trace)"""
        return self.get_events(correlation_id=correlation_id, limit=limit)

    # ================================================================================
    # ASYNC EVENT BUS OPERATIONS - Phase 4.1 Implementation
    # ================================================================================

    if ASYNC_AVAILABLE:

        async def publish_async(self, event: Event, correlation_id: str = None) -> str:
            """
            Async version of publish for high-performance event publishing.

            Args:
                event: Event to publish
                correlation_id: Optional correlation ID for workflow tracking

            Returns:
                Event ID of published event
            """
            try:
                # Set correlation ID if provided
                if correlation_id:
                    event.correlation_id = correlation_id

                # Store event in database asynchronously
                async with get_async_connection() as conn:
                    await conn.execute(
                        """,
                        INSERT INTO events (
                            event_id, event_type, timestamp, source_agent,
                            correlation_id, payload, metadata
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                        (
                            event.event_id,
                            event.event_type,
                            event.timestamp.isoformat(),
                            event.source_agent,
                            event.correlation_id,
                            json.dumps(event.payload),
                            json.dumps(event.metadata),
                        ),
                    )
                    await conn.commit()

                # Notify subscribers asynchronously
                await self._notify_subscribers_async(event)

                logger.debug(f"Published async event {event.event_id}: {event.event_type}")
                return event.event_id

            except Exception as e:
                logger.error(f"Failed to publish async event {event.event_type}: {e}")
                raise EventPublishError(f"Async event publishing failed: {e}") from e

        async def get_events_async(
            self, event_type: str = None, correlation_id: str = None, source_agent: str = None, limit: int = 100,
        ) -> list[Event]:
            """
            Async version of get_events for high-performance event retrieval.

            Args:
                event_type: Filter by event type
                correlation_id: Filter by correlation ID
                source_agent: Filter by source agent
                limit: Maximum number of events to return

            Returns:
                List of matching events
            """
            try:
                # Build dynamic query
                where_clauses = []
                params = []

                if event_type:
                    where_clauses.append("event_type = ?")
                    params.append(event_type)

                if correlation_id:
                    where_clauses.append("correlation_id = ?")
                    params.append(correlation_id)

                if source_agent:
                    where_clauses.append("source_agent = ?")
                    params.append(source_agent)

                where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
                params.append(limit)

                async with get_async_connection() as conn:
                    cursor = await conn.execute(
                        f""",
                        SELECT * FROM events,
                        WHERE {where_sql}
                        ORDER BY timestamp DESC,
                        LIMIT ?
                    """,
                        params,
                    )

                    rows = await cursor.fetchall()

                events = []
                for row in rows:
                    event_data = dict(row)
                    event_data["payload"] = json.loads(event_data["payload"])
                    event_data["metadata"] = json.loads(event_data["metadata"])
                    events.append(Event.from_dict(event_data))

                return events

            except Exception as e:
                logger.error(f"Failed to get async events: {e}")
                return []

        async def get_event_history_async(self, correlation_id: str) -> list[Event]:
            """
            Async version of get_event_history for workflow tracing.

            Args:
                correlation_id: Correlation ID to trace

            Returns:
                List of events in chronological order
            """
            try:
                async with get_async_connection() as conn:
                    cursor = await conn.execute(
                        """,
                        SELECT * FROM events,
                        WHERE correlation_id = ?,
                        ORDER BY timestamp ASC,
                    """,
                        (correlation_id,),
                    )

                    rows = await cursor.fetchall()

                events = []
                for row in rows:
                    event_data = dict(row)
                    event_data["payload"] = json.loads(event_data["payload"])
                    event_data["metadata"] = json.loads(event_data["metadata"])
                    events.append(Event.from_dict(event_data))

                return events

            except Exception as e:
                logger.error(f"Failed to get async event history for {correlation_id}: {e}")
                return []

        async def _notify_subscribers_async(self, event: Event) -> None:
            """Notify subscribers asynchronously."""
            try:
                # Get matching subscribers
                matching_subscribers = []
                with self._subscriber_lock:
                    for pattern, subscribers in self._subscribers.items():
                        if self._pattern_matches(pattern, event.event_type):
                            matching_subscribers.extend(subscribers)

                # Notify subscribers concurrently
                if matching_subscribers:
                    notification_tasks = [
                        self._notify_single_subscriber_async(subscriber, event) for subscriber in matching_subscribers
                    ]
                    await asyncio.gather(*notification_tasks, return_exceptions=True)

            except Exception as e:
                logger.error(f"Error in async subscriber notification: {e}")

        async def _notify_single_subscriber_async(self, subscriber: EventSubscriber, event: Event) -> None:
            """Notify a single subscriber asynchronously."""
            try:
                # Check if callback is async
                if asyncio.iscoroutinefunction(subscriber.callback):
                    await subscriber.callback(event)
                else:
                    # Run sync callback in thread pool to avoid blocking
                    loop = asyncio.get_event_loop()
                    await loop.run_in_executor(None, subscriber.callback, event)

            except Exception as e:
                logger.error(f"Error notifying async subscriber {subscriber.subscriber_name}: {e}")

    def clear_old_events(self, days_to_keep: int = 30) -> None:
        """Clean up old events to prevent database growth"""
        cutoff_date = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        cutoff_date = cutoff_date.replace(day=cutoff_date.day - days_to_keep)

        with get_sqlite_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM events WHERE timestamp < ?", (cutoff_date.isoformat(),))
            deleted_count = cursor.rowcount
            conn.commit()

        logger.info(f"Cleaned up {deleted_count} old events")
        return deleted_count


# Global event bus instance
_event_bus: EventBus | None = None
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


def reset_event_bus() -> None:
    """Reset the global event bus (for testing)"""
    global _event_bus
    _event_bus = None


# Async support for Phase 4.1
if ASYNC_AVAILABLE:

    async def get_async_event_bus_async() -> EventBus:
        """Get the global event bus instance for async operations"""
        return get_event_bus()  # Same instance, just async access pattern

    async def publish_event_async(event: Event, correlation_id: str = None) -> str:
        """Convenience function for async event publishing"""
        bus = await get_async_event_bus_async()
        return await bus.publish_async(event, correlation_id)

    async def get_events_async(**kwargs) -> list[Event]:
        """Convenience function for async event retrieval"""
        bus = await get_async_event_bus_async()
        return await bus.get_events_async(**kwargs)

    async def get_event_history_async(correlation_id: str) -> list[Event]:
        """Convenience function for async event history retrieval"""
        bus = await get_async_event_bus_async()
        return await bus.get_event_history_async(correlation_id)
