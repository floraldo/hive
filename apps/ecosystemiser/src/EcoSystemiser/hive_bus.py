"""
Hive Bus integration for EcoSystemiser.

This module provides the event bus integration for EcoSystemiser,
connecting it to the broader Hive ecosystem's event-driven architecture.

When the full hive-orchestrator is available, this will import from there.
For now, it provides a working stub implementation.
"""

import json
from hive_logging import get_logger
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timezone
from dataclasses import dataclass, field
from pathlib import Path
import uuid
from EcoSystemiser.db.connection import ecosystemiser_transaction, get_ecosystemiser_db_path
from EcoSystemiser.db.schema import ensure_database_schema

logger = get_logger(__name__)

# Try to import from the real hive-orchestrator if available
try:
    from hive_orchestrator.core.bus.hive_bus import HiveEventBus
    from hive_orchestrator.core.bus.hive_events import BaseEvent, TaskEvent, WorkflowEvent
    REAL_HIVE_BUS = True
except ImportError:
    REAL_HIVE_BUS = False
    logger.info("Using stub hive_bus implementation. Real implementation not yet available.")


@dataclass
class Event:
    """Base event class for Hive event system."""

    event_type: str
    source_agent: str
    timestamp: Optional[datetime] = None
    event_id: Optional[str] = None
    correlation_id: Optional[str] = None
    payload: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc)
        if not self.event_id:
            self.event_id = str(uuid.uuid4())

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary."""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "source_agent": self.source_agent,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "correlation_id": self.correlation_id,
            "payload": self.payload,
            "metadata": self.metadata
        }


class WorkflowEventType:
    """Standard workflow event types."""
    STARTED = "workflow.started"
    COMPLETED = "workflow.completed"
    FAILED = "workflow.failed"
    PROGRESS = "workflow.progress"


class TaskEventType:
    """Standard task event types."""
    CREATED = "task.created"
    STARTED = "task.started"
    COMPLETED = "task.completed"
    FAILED = "task.failed"
    RETRYING = "task.retrying"


def create_workflow_event(
    event_type: str,
    workflow_id: str = None,
    source_agent: str = "ecosystemiser",
    correlation_id: str = None,
    **payload
) -> Event:
    """Create a workflow event."""
    return Event(
        event_type=event_type,
        source_agent=source_agent,
        correlation_id=correlation_id or workflow_id,
        payload={
            "workflow_id": workflow_id,
            **payload
        }
    )


def create_task_event(
    event_type: str,
    task_id: str,
    source_agent: str = "ecosystemiser",
    correlation_id: str = None,
    **payload
) -> Event:
    """Create a task event."""
    return Event(
        event_type=event_type,
        source_agent=source_agent,
        correlation_id=correlation_id,
        payload={
            "task_id": task_id,
            **payload
        }
    )


class EventBus:
    """
    Event bus for publish/subscribe messaging.

    This is a stub implementation that will be replaced with
    the real HiveEventBus when available.
    """

    def __init__(self):
        """Initialize the event bus."""
        self.subscribers = {}
        self.events = []
        self._is_real = REAL_HIVE_BUS
        self.db_path = get_ecosystemiser_db_path()

        # Ensure EcoSystemiser database schema exists
        ensure_database_schema()

        if REAL_HIVE_BUS:
            # We don't use the orchestrator's HiveEventBus directly
            # We maintain our own event storage in ecosystemiser.db
            self._real_bus = None
        else:
            self._real_bus = None

    def publish(self, event: Event) -> str:
        """
        Publish an event to the bus.

        Args:
            event: Event to publish

        Returns:
            Event ID of the published event
        """
        # Store in EcoSystemiser database
        try:
            with ecosystemiser_transaction(self.db_path) as conn:
                conn.execute("""
                    INSERT INTO ecosystemiser_events
                    (event_id, event_type, source_agent, timestamp, correlation_id, payload, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    event.event_id,
                    event.event_type,
                    event.source_agent,
                    event.timestamp.isoformat() if event.timestamp else None,
                    event.correlation_id,
                    json.dumps(event.payload),
                    json.dumps(event.metadata)
                ))
        except Exception as e:
            logger.error(f"Failed to store event in database: {e}")

        # Also keep in memory for subscribers
        self.events.append(event)

        # Notify subscribers
        event_type = event.event_type
        if event_type in self.subscribers:
            for callback in self.subscribers[event_type]:
                try:
                    callback(event)
                except Exception as e:
                    logger.error(f"Subscriber callback failed: {e}")

        # Also check for wildcard subscribers
        if "*" in self.subscribers:
            for callback in self.subscribers["*"]:
                try:
                    callback(event)
                except Exception as e:
                    logger.error(f"Wildcard subscriber callback failed: {e}")

        return event.event_id

    def subscribe(self, event_type: str, callback: Callable[[Event], None]):
        """
        Subscribe to events of a specific type.

        Args:
            event_type: Type of event to subscribe to (or "*" for all)
            callback: Function to call when event is published
        """
        if self._real_bus:
            # Wrap callback to convert dict to Event
            def wrapped_callback(event_data):
                event = Event(**event_data) if isinstance(event_data, dict) else event_data
                callback(event)
            self._real_bus.subscribe(event_type, wrapped_callback)
            return

        # Stub implementation
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []
        self.subscribers[event_type].append(callback)

    def get_events(
        self,
        event_type: Optional[str] = None,
        since: Optional[datetime] = None,
        correlation_id: Optional[str] = None
    ) -> List[Event]:
        """
        Get events from the bus.

        Args:
            event_type: Filter by event type
            since: Filter events after this time
            correlation_id: Filter by correlation ID

        Returns:
            List of matching events
        """
        # Read from EcoSystemiser database
        try:
            with ecosystemiser_transaction(self.db_path) as conn:
                query = "SELECT * FROM ecosystemiser_events WHERE 1=1"
                params = []

                if event_type:
                    query += " AND event_type = ?"
                    params.append(event_type)

                if since:
                    query += " AND timestamp >= ?"
                    params.append(since.isoformat() if hasattr(since, 'isoformat') else str(since))

                if correlation_id:
                    query += " AND correlation_id = ?"
                    params.append(correlation_id)

                query += " ORDER BY timestamp DESC"

                cursor = conn.execute(query, params)
                rows = cursor.fetchall()

                events = []
                for row in rows:
                    event = Event(
                        event_id=row["event_id"],
                        event_type=row["event_type"],
                        source_agent=row["source_agent"],
                        timestamp=datetime.fromisoformat(row["timestamp"]) if row["timestamp"] else None,
                        correlation_id=row["correlation_id"],
                        payload=json.loads(row["payload"]) if row["payload"] else {},
                        metadata=json.loads(row["metadata"]) if row["metadata"] else {}
                    )
                    events.append(event)

                return events

        except Exception as e:
            logger.error(f"Failed to retrieve events from database: {e}")
            # Fallback to in-memory events
            results = self.events

            if event_type:
                results = [e for e in results if e.event_type == event_type]

            if since:
                results = [e for e in results if e.timestamp >= since]

            if correlation_id:
                results = [e for e in results if e.correlation_id == correlation_id]

            return results

    def clear(self):
        """Clear all events (stub only)."""
        if not self._real_bus:
            self.events = []
            self.subscribers = {}


# Global event bus instance
_event_bus = None


def get_event_bus() -> EventBus:
    """Get the global event bus instance."""
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus


# Export the main classes and functions
__all__ = [
    "Event",
    "EventBus",
    "WorkflowEventType",
    "TaskEventType",
    "create_workflow_event",
    "create_task_event",
    "get_event_bus"
]