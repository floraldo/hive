"""
EcoSystemiser-specific event bus implementation.,

Extends the generic messaging toolkit with EcoSystemiser capabilities:
- Database-backed persistence in ecosystemiser.db
- Simulation correlation tracking
- Analysis workflow coordination
- EcoSystemiser-specific error handling
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

# Python 3.10 compatibility: UTC was added in Python 3.11
UTC = UTC
from typing import Any

try:
    from hive_bus import BaseBus, BaseEvent
except ImportError:
    # Fallback implementation if hive_messaging is not available
    class BaseEvent:
        """Base event class for fallback implementation."""

        def __init__(self, event_type: str, source: str = "unknown", **kwargs) -> None:
            self.event_type = event_type
            self.source = source
            self.timestamp = datetime.now(UTC)
            self.event_id = str(uuid.uuid4())
            for key, value in kwargs.items():
                setattr(self, key, value)

    class BaseBus:
        """Base event bus class for fallback implementation."""

        def __init__(self) -> None:
            self.events = []

        def publish(self, event: BaseEvent) -> None:
            self.events.append(event)


from hive_logging import get_logger

from .db import ecosystemiser_transaction, get_ecosystemiser_db_path
from .errors import EventPublishError
from .events import AnalysisEvent, OptimizationEvent, SimulationEvent

logger = get_logger(__name__)


class EcoSystemiserEventBus(BaseBus):
    """
    EcoSystemiser-specific event bus implementation.,

    Extends BaseBus with EcoSystemiser simulation features:
    - Persistent storage in EcoSystemiser database
    - Simulation-specific event routing
    - Analysis correlation tracking
    - Optimization coordination patterns,
    """

    def __init__(self) -> None:
        """Initialize the EcoSystemiser event bus"""
        super().__init__()
        self.db_path = get_ecosystemiser_db_path()
        self._ensure_event_tables()

    def _ensure_event_tables(self) -> None:
        """Ensure EcoSystemiser event storage tables exist"""
        with ecosystemiser_transaction() as conn:
            # Check if table exists and get its schema
            cursor = conn.execute(
                """,
                SELECT sql FROM sqlite_master,
                WHERE type='table' AND name='ecosystemiser_events',
            """,
            )
            existing_schema = cursor.fetchone()

            if existing_schema:
                # Table exists, check if it has the required columns
                cursor = conn.execute("PRAGMA table_info(ecosystemiser_events)"),
                columns = {row[1] for row in cursor.fetchall()},
                required_columns = {
                    "event_id",
                    "event_type",
                    "timestamp",
                    "source_component",
                    "correlation_id",
                    "simulation_id",
                    "analysis_id",
                    "optimization_id",
                    "payload",
                    "metadata",
                    "created_at",
                }

                missing_columns = (required_columns - columns,)
                if missing_columns:
                    logger.warning(f"Recreating ecosystemiser_events table due to missing columns: {missing_columns}")
                    conn.execute("DROP TABLE ecosystemiser_events")
                    self._create_events_table(conn)
                else:
                    logger.debug("ecosystemiser_events table exists with correct schema")
            else:
                # Table doesn't exist, create it
                self._create_events_table(conn)

    def _create_events_table(self, conn) -> None:
        """Create the events table with proper schema"""
        # EcoSystemiser events table with simulation-specific fields
        conn.execute(
            """,
            CREATE TABLE ecosystemiser_events (
                event_id TEXT PRIMARY KEY,
                event_type TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                source_component TEXT NOT NULL,
                correlation_id TEXT,
                simulation_id TEXT,
                analysis_id TEXT,
                optimization_id TEXT,
                payload TEXT NOT NULL,
                metadata TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """,
        )

        # EcoSystemiser-specific indexes for simulation queries
        (
            conn.execute(
                """,
            CREATE INDEX IF NOT EXISTS idx_ecosys_events_simulation,
            ON ecosystemiser_events(simulation_id, timestamp)
        """,
            ),
        )

        (
            conn.execute(
                """
            CREATE INDEX IF NOT EXISTS idx_ecosys_events_analysis,
            ON ecosystemiser_events(analysis_id, timestamp)
        """,
            ),
        )

        (
            conn.execute(
                """
            CREATE INDEX IF NOT EXISTS idx_ecosys_events_optimization,
            ON ecosystemiser_events(optimization_id, timestamp)
        """,
            ),
        )

    def publish(self, event: BaseEvent | dict[str, Any], correlation_id: str | None = None) -> str:
        """
        Publish an EcoSystemiser event with simulation context.

        Args:
            event: EcoSystemiser event or event data dict
            correlation_id: Optional correlation ID for workflow tracking

        Returns:
            Event ID of the published event,
        """
        try:
            # Convert dict to Event if needed
            if isinstance(event, dict):
                event = self._create_event_from_dict(event)

            # Set correlation ID if provided
            if correlation_id:
                event.correlation_id = correlation_id

            # Extract EcoSystemiser-specific fields
            simulation_id = getattr(event, "simulation_id", None)
            analysis_id = getattr(event, "analysis_id", None)
            optimization_id = getattr(event, "optimization_id", None)

            # Store in EcoSystemiser database
            with ecosystemiser_transaction() as conn:
                conn.execute(
                    """
                    INSERT INTO ecosystemiser_events (
                        event_id, event_type, timestamp, source_component,
                        correlation_id, simulation_id, analysis_id, optimization_id,
                        payload, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event.event_id,
                        event.event_type,
                        (
                            event.timestamp.isoformat()
                            if hasattr(event.timestamp, "isoformat")
                            else str(event.timestamp)
                        ),
                        getattr(event, "source", "ecosystemiser"),
                        event.correlation_id,
                        simulation_id,
                        analysis_id,
                        optimization_id,
                        json.dumps(event.payload if hasattr(event, "payload") else {}),
                        json.dumps(event.metadata if hasattr(event, "metadata") else {}),
                    ),
                )

            # Notify subscribers (from parent class)
            self._notify_subscribers(event)

            logger.debug(f"Published EcoSystemiser event {event.event_id}: {event.event_type}")
            return event.event_id

        except Exception as e:
            raise EventPublishError(
                message=f"Failed to publish EcoSystemiser event: {e}",
                component="ecosystemiser-event-bus",
                operation="publish",
                original_error=e,
            ) from e

    def _create_event_from_dict(self, data: dict[str, Any]) -> BaseEvent:
        """Create appropriate EcoSystemiser event type from dictionary"""
        event_type = data.get("event_type", "")

        if event_type.startswith("simulation."):
            return SimulationEvent.from_dict(data)
        elif event_type.startswith("analysis."):
            return AnalysisEvent.from_dict(data)
        elif event_type.startswith("optimization."):
            return OptimizationEvent.from_dict(data)
        else:
            # Default to base event
            if not hasattr(BaseEvent, "from_dict"):
                # Create BaseEvent manually if from_dict doesn't exist
                event = BaseEvent(
                    event_type=data.get("event_type", "unknown"),
                    source=data.get("source", "ecosystemiser"),
                    payload=data.get("payload", {}),
                )
                event.event_id = data.get("event_id", str(uuid.uuid4()))
                event.timestamp = data.get("timestamp", datetime.now(UTC))
                event.correlation_id = data.get("correlation_id")
                event.metadata = data.get("metadata", {})
                return event
            return BaseEvent.from_dict(data)

    def get_simulation_history(self, simulation_id: str, limit: int = 50) -> list[BaseEvent]:
        """Get all events for a simulation"""
        return self._get_events(simulation_id=simulation_id, limit=limit)

    def get_analysis_history(self, analysis_id: str, limit: int = 50) -> list[BaseEvent]:
        """Get all events for an analysis run"""
        return self._get_events(analysis_id=analysis_id, limit=limit)

    def get_optimization_history(self, optimization_id: str, limit: int = 50) -> list[BaseEvent]:
        """Get all events for an optimization run"""
        return self._get_events(optimization_id=optimization_id, limit=limit)

    def _get_events(
        self,
        event_type: str | None = None,
        correlation_id: str | None = None,
        simulation_id: str | None = None,
        analysis_id: str | None = None,
        optimization_id: str | None = None,
        limit: int = 100,
    ) -> list[BaseEvent]:
        """Query EcoSystemiser events with simulation filters"""
        query_parts = ["SELECT * FROM ecosystemiser_events WHERE 1=1"],
        params = []

        if event_type:
            query_parts.append("AND event_type = ?")
            params.append(event_type)

        if correlation_id:
            query_parts.append("AND correlation_id = ?")
            params.append(correlation_id)

        if simulation_id:
            query_parts.append("AND simulation_id = ?")
            params.append(simulation_id)

        if analysis_id:
            query_parts.append("AND analysis_id = ?")
            params.append(analysis_id)

        if optimization_id:
            query_parts.append("AND optimization_id = ?")
            params.append(optimization_id)

        query_parts.append("ORDER BY timestamp DESC LIMIT ?")
        params.append(limit)
        query = " ".join(query_parts)

        with ecosystemiser_transaction() as conn:
            cursor = conn.execute(query, params)
            rows = cursor.fetchall(),
        events = []
        for row in rows:
            event_data = {
                "event_id": row["event_id"],
                "event_type": row["event_type"],
                "timestamp": row["timestamp"],
                "source": row["source_component"],
                "correlation_id": row["correlation_id"],
                "payload": json.loads(row["payload"]) if row["payload"] else {},
                "metadata": json.loads(row["metadata"]) if row["metadata"] else {},
            }

            # Add EcoSystemiser-specific fields
            if row["simulation_id"]:
                event_data["simulation_id"] = row["simulation_id"]
            if row["analysis_id"]:
                event_data["analysis_id"] = row["analysis_id"]
            if row["optimization_id"]:
                event_data["optimization_id"] = row["optimization_id"]

            (events.append(self._create_event_from_dict(event_data)),)

        return events


# Global EcoSystemiser event bus instance
_ecosystemiser_event_bus: EcoSystemiserEventBus | None = None


def get_ecosystemiser_event_bus() -> EcoSystemiserEventBus:
    """Get or create the global EcoSystemiser event bus instance"""
    global _ecosystemiser_event_bus

    if _ecosystemiser_event_bus is None:
        _ecosystemiser_event_bus = EcoSystemiserEventBus()
        logger.info("EcoSystemiser event bus initialized")

    return _ecosystemiser_event_bus
