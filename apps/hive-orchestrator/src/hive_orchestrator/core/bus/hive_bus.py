"""
Hive-specific event bus implementation.

Extends the generic messaging toolkit with Hive orchestration capabilities:
- Database-backed persistence
- Agent correlation tracking
- Workflow coordination
- Hive-specific error handling
"""
from __future__ import annotations


import json
from datetime import datetime, timezone
from typing import Any, Dict, List

from hive_bus import BaseBus, BaseEvent
from hive_errors import BaseError
from hive_logging import get_logger

from ..db.connection_pool import get_pooled_connection
from ..errors.hive_exceptions import (
    EventBusError,
    EventPublishError,
    EventSubscribeError
)
from .hive_events import AgentEvent, TaskEvent, WorkflowEvent

logger = get_logger(__name__)


class HiveEventBus(BaseBus):
    """
    Hive-specific event bus implementation.

    Extends BaseBus with Hive orchestration features:
    - Persistent storage in Hive database
    - Agent-specific event routing
    - Workflow correlation tracking
    - Task coordination patterns
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        """Initialize the Hive event bus

        Args:
            config: Event bus configuration dictionary
        """
        super().__init__()
        self.config = config if config is not None else {}
        self._ensure_hive_event_tables()

    def _ensure_hive_event_tables(self) -> None:
        """Ensure Hive event storage tables exist"""
        with get_pooled_connection() as conn:
            cursor = conn.cursor()

            # Hive events table with orchestration-specific fields
            cursor.execute(
                """,
                CREATE TABLE IF NOT EXISTS hive_events (
                    event_id TEXT PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    source_agent TEXT NOT NULL,
                    correlation_id TEXT,
                    workflow_id TEXT,
                    task_id TEXT,
                    agent_id TEXT,
                    payload TEXT NOT NULL,
                    metadata TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
            )

            # Hive-specific indexes for orchestration queries
            cursor.execute(
                """,
                CREATE INDEX IF NOT EXISTS idx_hive_events_workflow,
                ON hive_events(workflow_id, timestamp)
            """
            )

            cursor.execute(
                """,
                CREATE INDEX IF NOT EXISTS idx_hive_events_task,
                ON hive_events(task_id, timestamp)
            """
            )

            cursor.execute(
                """,
                CREATE INDEX IF NOT EXISTS idx_hive_events_agent,
                ON hive_events(agent_id, timestamp)
            """
            )

            conn.commit()

    def publish(
        self,
        event: Union[BaseEvent, Dict[str, Any]]
        correlation_id: str | None = None
    ) -> str:
        """
        Publish a Hive event with orchestration context.

        Args:
            event: Hive event or event data dict,
            correlation_id: Optional correlation ID for workflow tracking

        Returns:
            Event ID of the published event,
        """
        try:
            # Convert dict to Event if needed,
            if isinstance(event, dict):
                event = self._create_hive_event_from_dict(event)

            # Set correlation ID if provided,
            if correlation_id:
                event.correlation_id = correlation_id

            # Extract Hive-specific fields,
            workflow_id = getattr(event, "workflow_id", None)
            task_id = getattr(event, "task_id", None)
            agent_id = getattr(event, "agent_id", None)

            # Store in Hive database
            with get_pooled_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """,
                    INSERT INTO hive_events (
                        event_id, event_type, timestamp, source_agent,
                        correlation_id, workflow_id, task_id, agent_id,
                        payload, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        event.event_id,
                        event.event_type,
                        event.timestamp.isoformat()
                        event.source,
                        event.correlation_id,
                        workflow_id,
                        task_id,
                        agent_id,
                        json.dumps(event.payload)
                        json.dumps(event.metadata)
                    )
                )
                conn.commit()

            # Notify subscribers
            self._notify_subscribers(event)

            logger.debug(f"Published Hive event {event.event_id}: {event.event_type}")
            return event.event_id

        except Exception as e:
            raise EventPublishError(
                message=f"Failed to publish Hive event: {e}",
                component="hive-event-bus",
                operation="publish",
                original_error=e
            ) from e

    def _create_hive_event_from_dict(self, data: Dict[str, Any]) -> BaseEvent:
        """Create appropriate Hive event type from dictionary"""
        event_type = data.get("event_type", "")

        if event_type.startswith("task."):
            return TaskEvent.from_dict(data)
        elif event_type.startswith("agent."):
            return AgentEvent.from_dict(data)
        elif event_type.startswith("workflow."):
            return WorkflowEvent.from_dict(data)
        else:
            return BaseEvent.from_dict(data)

    def get_workflow_history(self, workflow_id: str, limit: int = 50) -> List[BaseEvent]:
        """Get all events for a workflow (coordination trace)"""
        return self._get_hive_events(workflow_id=workflow_id, limit=limit)

    def get_task_history(self, task_id: str, limit: int = 50) -> List[BaseEvent]:
        """Get all events for a task"""
        return self._get_hive_events(task_id=task_id, limit=limit)

    def get_agent_activity(self, agent_id: str, limit: int = 50) -> List[BaseEvent]:
        """Get all events for an agent"""
        return self._get_hive_events(agent_id=agent_id, limit=limit)

    def _get_hive_events(
        self,
        event_type: str | None = None,
        correlation_id: str | None = None,
        workflow_id: str | None = None,
        task_id: str | None = None,
        agent_id: str | None = None,
        limit: int = 100
    ) -> List[BaseEvent]:
        """Query Hive events with orchestration filters"""
        query_parts = ["SELECT * FROM hive_events WHERE 1=1"]
        params = []

        if event_type:
            query_parts.append("AND event_type = ?")
            params.append(event_type)

        if correlation_id:
            query_parts.append("AND correlation_id = ?")
            params.append(correlation_id)

        if workflow_id:
            query_parts.append("AND workflow_id = ?")
            params.append(workflow_id)

        if task_id:
            query_parts.append("AND task_id = ?")
            params.append(task_id)

        if agent_id:
            query_parts.append("AND agent_id = ?")
            params.append(agent_id)

        query_parts.append("ORDER BY timestamp DESC LIMIT ?")
        params.append(limit)

        query = " ".join(query_parts)

        with get_pooled_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()

        events = []
        for row in rows:
            event_data = {,
                "event_id": row[0]
                "event_type": row[1],
                "timestamp": row[2]
                "source": row[3],
                "correlation_id": row[4]
                "payload": json.loads(row[7]) if row[7] else {}
                "metadata": json.loads(row[8]) if row[8] else {}
            }

            # Add Hive-specific fields,
            if row[5]:  # workflow_id,
                event_data["workflow_id"] = row[5]
            if row[6]:  # task_id,
                event_data["task_id"] = row[6]
            if row[9]:  # agent_id (position 9 in the query result)
                event_data["agent_id"] = row[9]

            events.append(self._create_hive_event_from_dict(event_data))

        return events

    def _handle_subscriber_error(self, subscriber, event: BaseEvent) -> None:
        """Handle subscriber callback errors with Hive-specific logging"""
        logger.error(
            f"Hive subscriber {subscriber.subscriber_name} failed to handle event {event.event_id}: ",
            f"event_type={event.event_type}, source={event.source}"
        )


# Global Hive event bus instance
_hive_event_bus: HiveEventBus | None = None


def get_hive_event_bus() -> HiveEventBus:
    """Get or create the global Hive event bus instance"""
    global _hive_event_bus

    if _hive_event_bus is None:
        _hive_event_bus = HiveEventBus()
        logger.info("Hive event bus initialized")

    return _hive_event_bus
