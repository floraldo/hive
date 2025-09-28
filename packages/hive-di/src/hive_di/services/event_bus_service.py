"""
Event Bus Service Implementation

Injectable event bus service that replaces global event bus patterns.
Provides database-backed event messaging with proper dependency injection.
"""

import json
import uuid
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Callable, Union
from dataclasses import dataclass, asdict

from ..interfaces import IEventBusService, IDatabaseConnectionService, IConfigurationService, IDisposable


@dataclass
class Event:
    """Event data structure"""
    event_id: str
    event_type: str
    timestamp: datetime
    source_agent: str
    correlation_id: Optional[str]
    payload: Dict[str, Any]
    metadata: Dict[str, Any]


@dataclass
class EventSubscription:
    """Event subscription data structure"""
    subscription_id: str
    event_pattern: str
    subscriber_agent: str
    callback: Callable
    created_at: datetime


class EventBusService(IEventBusService, IDisposable):
    """
    Injectable event bus service

    Replaces global event bus patterns with a proper service that can be
    configured and injected independently.
    """

    def __init__(self,
                 configuration_service: IConfigurationService,
                 database_service: IDatabaseConnectionService,
                 config: Optional[Dict[str, Any]] = None):
        """
        Initialize event bus service

        Args:
            configuration_service: Configuration service for getting event bus settings
            database_service: Database service for event persistence
            config: Optional override configuration
        """
        self._config_service = configuration_service
        self._db_service = database_service
        self._override_config = config or {}

        # Get event bus configuration
        bus_config = self._config_service.get_event_bus_config()
        self._config = {**bus_config, **self._override_config}

        # Event bus settings
        self.max_events_in_memory = self._config.get('max_events_in_memory', 1000)
        self.event_retention_days = self._config.get('event_retention_days', 30)
        self.enable_async = self._config.get('enable_async', True)

        # In-memory subscriptions
        self._subscriptions: Dict[str, EventSubscription] = {}
        self._subscription_lock = threading.RLock()

        # Initialize database tables
        self._ensure_event_tables()

    def _ensure_event_tables(self) -> None:
        """Ensure event storage tables exist"""
        with self._db_service.get_pooled_connection() as conn:
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
                    is_active BOOLEAN DEFAULT TRUE
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
                CREATE INDEX IF NOT EXISTS idx_events_source
                ON events(source_agent, timestamp)
            """)

            conn.commit()

    def _create_event_id(self) -> str:
        """Create a unique event ID"""
        return str(uuid.uuid4())

    def _create_subscription_id(self) -> str:
        """Create a unique subscription ID"""
        return str(uuid.uuid4())

    def _pattern_matches(self, pattern: str, event_type: str) -> bool:
        """Check if an event type matches a subscription pattern"""
        # Simple wildcard matching for now
        # Can be enhanced with more sophisticated pattern matching
        if pattern == "*":
            return True
        if pattern.endswith("*"):
            return event_type.startswith(pattern[:-1])
        return pattern == event_type

    def _notify_subscribers(self, event: Event) -> None:
        """Notify all matching subscribers of an event"""
        with self._subscription_lock:
            for subscription in self._subscriptions.values():
                if self._pattern_matches(subscription.event_pattern, event.event_type):
                    try:
                        # Call subscriber callback in a separate thread to avoid blocking
                        import threading
                        thread = threading.Thread(
                            target=self._safe_callback,
                            args=(subscription.callback, event),
                            daemon=True
                        )
                        thread.start()
                    except Exception:
                        # Log error but don't let it break event publishing
                        pass

    def _safe_callback(self, callback: Callable, event: Event) -> None:
        """Safely call a subscriber callback"""
        try:
            callback(asdict(event))
        except Exception:
            # Log error but don't propagate - subscriber errors shouldn't break the bus
            pass

    # IEventBusService interface implementation

    def publish(self, event_type: str, payload: Dict[str, Any],
                source_agent: str, correlation_id: Optional[str] = None) -> str:
        """Publish an event to the bus"""
        event_id = self._create_event_id()
        timestamp = datetime.now(timezone.utc)

        event = Event(
            event_id=event_id,
            event_type=event_type,
            timestamp=timestamp,
            source_agent=source_agent,
            correlation_id=correlation_id,
            payload=payload,
            metadata={}
        )

        # Store in database
        with self._db_service.get_pooled_connection() as conn:
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

        return event_id

    async def publish_async(self, event_type: str, payload: Dict[str, Any],
                           source_agent: str, correlation_id: Optional[str] = None) -> str:
        """Publish an event asynchronously"""
        if not self.enable_async:
            return self.publish(event_type, payload, source_agent, correlation_id)

        event_id = self._create_event_id()
        timestamp = datetime.now(timezone.utc)

        event = Event(
            event_id=event_id,
            event_type=event_type,
            timestamp=timestamp,
            source_agent=source_agent,
            correlation_id=correlation_id,
            payload=payload,
            metadata={}
        )

        # Store in database (async)
        async with self._db_service.get_async_pooled_connection() as conn:
            await conn.execute("""
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
            await conn.commit()

        # Notify subscribers
        self._notify_subscribers(event)

        return event_id

    def subscribe(self, event_pattern: str, callback: Callable, subscriber_agent: str) -> str:
        """Subscribe to events matching a pattern"""
        subscription_id = self._create_subscription_id()

        subscription = EventSubscription(
            subscription_id=subscription_id,
            event_pattern=event_pattern,
            subscriber_agent=subscriber_agent,
            callback=callback,
            created_at=datetime.now(timezone.utc)
        )

        with self._subscription_lock:
            self._subscriptions[subscription_id] = subscription

        # Optionally store in database for persistence across restarts
        with self._db_service.get_pooled_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO event_subscriptions (
                    subscription_id, event_pattern, subscriber_agent,
                    callback_info, created_at, is_active
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                subscription_id,
                event_pattern,
                subscriber_agent,
                "in_memory_callback",  # Can't serialize callback
                subscription.created_at.isoformat(),
                True
            ))
            conn.commit()

        return subscription_id

    def unsubscribe(self, subscription_id: str) -> bool:
        """Unsubscribe from events"""
        with self._subscription_lock:
            if subscription_id in self._subscriptions:
                del self._subscriptions[subscription_id]

                # Mark as inactive in database
                with self._db_service.get_pooled_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        UPDATE event_subscriptions
                        SET is_active = FALSE
                        WHERE subscription_id = ?
                    """, (subscription_id,))
                    conn.commit()

                return True
            return False

    def get_events(self, event_type: Optional[str] = None,
                   since: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """Get events from the bus"""
        with self._db_service.get_pooled_connection() as conn:
            cursor = conn.cursor()

            if event_type and since:
                cursor.execute("""
                    SELECT * FROM events
                    WHERE event_type = ? AND timestamp >= ?
                    ORDER BY timestamp DESC
                """, (event_type, since.isoformat()))
            elif event_type:
                cursor.execute("""
                    SELECT * FROM events
                    WHERE event_type = ?
                    ORDER BY timestamp DESC
                """, (event_type,))
            elif since:
                cursor.execute("""
                    SELECT * FROM events
                    WHERE timestamp >= ?
                    ORDER BY timestamp DESC
                """, (since.isoformat(),))
            else:
                cursor.execute("""
                    SELECT * FROM events
                    ORDER BY timestamp DESC
                    LIMIT ?
                """, (self.max_events_in_memory,))

            rows = cursor.fetchall()

        events = []
        for row in rows:
            event_dict = dict(row)
            event_dict['payload'] = json.loads(event_dict['payload'])
            event_dict['metadata'] = json.loads(event_dict['metadata'])
            events.append(event_dict)

        return events

    def replay_events(self, correlation_id: str) -> List[Dict[str, Any]]:
        """Replay events for a correlation ID"""
        with self._db_service.get_pooled_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM events
                WHERE correlation_id = ?
                ORDER BY timestamp ASC
            """, (correlation_id,))
            rows = cursor.fetchall()

        events = []
        for row in rows:
            event_dict = dict(row)
            event_dict['payload'] = json.loads(event_dict['payload'])
            event_dict['metadata'] = json.loads(event_dict['metadata'])
            events.append(event_dict)

        return events

    # IDisposable interface implementation

    def dispose(self) -> None:
        """Clean up event bus service resources"""
        with self._subscription_lock:
            self._subscriptions.clear()

    # Additional utility methods

    def get_subscription_count(self) -> int:
        """Get number of active subscriptions"""
        with self._subscription_lock:
            return len(self._subscriptions)

    def get_event_count(self, since: Optional[datetime] = None) -> int:
        """Get total number of events"""
        with self._db_service.get_pooled_connection() as conn:
            cursor = conn.cursor()
            if since:
                cursor.execute("""
                    SELECT COUNT(*) FROM events WHERE timestamp >= ?
                """, (since.isoformat(),))
            else:
                cursor.execute("SELECT COUNT(*) FROM events")
            return cursor.fetchone()[0]

    def cleanup_old_events(self) -> int:
        """Clean up events older than retention period"""
        cutoff_date = datetime.now(timezone.utc).replace(
            day=datetime.now(timezone.utc).day - self.event_retention_days
        )

        with self._db_service.get_pooled_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM events WHERE timestamp < ?
            """, (cutoff_date.isoformat(),))
            deleted_count = cursor.rowcount
            conn.commit()

        return deleted_count

    def get_statistics(self) -> Dict[str, Any]:
        """Get event bus statistics"""
        return {
            'active_subscriptions': self.get_subscription_count(),
            'total_events': self.get_event_count(),
            'recent_events': self.get_event_count(
                datetime.now(timezone.utc).replace(hour=0, minute=0, second=0)
            ),
            'async_enabled': self.enable_async,
            'max_events_in_memory': self.max_events_in_memory,
            'event_retention_days': self.event_retention_days
        }