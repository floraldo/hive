"""Test hive-bus integration for EcoSystemiser."""

import pytest
import tempfile
import os
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from ecosystemiser.core.bus import (
    get_ecosystemiser_event_bus, EcoSystemiserEventBus
)
from ecosystemiser.core.events import (
    SimulationEvent, StudyEvent, AnalysisEvent
)


class TestEventBus:
    """Test the event bus implementation."""

    @pytest.fixture(autouse=True)
    def setup_temp_db(self):
        """Use a temporary database for each test."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_ecosystemiser.db"
            # Set environment variable to use temp database
            old_path = os.environ.get('ECOSYSTEMISER_DB_PATH')
            os.environ['ECOSYSTEMISER_DB_PATH'] = str(db_path)

            yield

            # Restore original environment
            if old_path:
                os.environ['ECOSYSTEMISER_DB_PATH'] = old_path
            else:
                del os.environ['ECOSYSTEMISER_DB_PATH']

    def test_event_creation(self):
        """Test creating a simulation event."""
        event = SimulationEvent.started(
            simulation_id="test_sim_123",
            config={"key": "value"}
        )

        assert event.event_type == "simulation.started"
        assert event.simulation_id == "test_sim_123"
        assert event.payload["config"] == {"key": "value"}
        assert event.event_id is not None
        assert event.timestamp is not None

    def test_workflow_event_creation(self):
        """Test creating a workflow event."""
        event = create_workflow_event(
            event_type=WorkflowEventType.STARTED,
            workflow_id="wf-123",
            source_agent="test",
            status="running"
        )

        assert event.event_type == WorkflowEventType.STARTED
        assert event.payload["workflow_id"] == "wf-123"
        assert event.payload["status"] == "running"

    def test_task_event_creation(self):
        """Test creating a task event."""
        event = create_task_event(
            event_type=TaskEventType.CREATED,
            task_id="task-456",
            source_agent="test",
            task_name="Process data"
        )

        assert event.event_type == TaskEventType.CREATED
        assert event.payload["task_id"] == "task-456"
        assert event.payload["task_name"] == "Process data"

    def test_event_bus_publish_subscribe(self):
        """Test publishing and subscribing to events."""
        bus = EventBus()
        received_events = []

        # Subscribe to events
        def handler(event):
            received_events.append(event)

        bus.subscribe("test.event", handler)

        # Publish an event
        event = Event(
            event_type="test.event",
            source_agent="test",
            payload={"data": "test"}
        )
        event_id = bus.publish(event)

        # Check event was received
        assert len(received_events) == 1
        assert received_events[0].event_type == "test.event"
        assert received_events[0].payload["data"] == "test"
        assert event_id == event.event_id

    def test_event_bus_wildcard_subscription(self):
        """Test subscribing to all events with wildcard."""
        bus = EventBus()
        received_events = []

        # Subscribe to all events
        def handler(event):
            received_events.append(event)

        bus.subscribe("*", handler)

        # Publish different event types
        event1 = Event(event_type="type.one", source_agent="test")
        event2 = Event(event_type="type.two", source_agent="test")

        bus.publish(event1)
        bus.publish(event2)

        # Check all events were received
        assert len(received_events) == 2
        assert received_events[0].event_type == "type.one"
        assert received_events[1].event_type == "type.two"

    def test_event_bus_get_events(self):
        """Test retrieving events from the bus."""
        bus = EventBus()

        # Publish some events
        event1 = Event(
            event_type="test.one",
            source_agent="test",
            correlation_id="corr-123"
        )
        event2 = Event(
            event_type="test.two",
            source_agent="test",
            correlation_id="corr-456"
        )
        event3 = Event(
            event_type="test.one",
            source_agent="test",
            correlation_id="corr-123"
        )

        bus.publish(event1)
        bus.publish(event2)
        bus.publish(event3)

        # Get all events
        all_events = bus.get_events()
        assert len(all_events) == 3

        # Get events by type
        type_one_events = bus.get_events(event_type="test.one")
        assert len(type_one_events) == 2

        # Get events by correlation ID
        corr_events = bus.get_events(correlation_id="corr-123")
        assert len(corr_events) == 2

    def test_global_event_bus(self):
        """Test the global event bus singleton."""
        bus1 = get_event_bus()
        bus2 = get_event_bus()

        # Should be the same instance
        assert bus1 is bus2


class TestEcoSystemiserEvents:
    """Test EcoSystemiser-specific events."""

    def test_simulation_event(self):
        """Test creating a simulation event."""
        event = create_simulation_event(
            event_type=EcoSystemiserEventType.SIMULATION_STARTED,
            simulation_id="sim-789",
            source_agent="ecosystemiser",
            system_config_path="/path/to/config.yml",
            solver_type="MILP"
        )

        assert event.simulation_id == "sim-789"
        assert event.system_config_path == "/path/to/config.yml"
        assert event.solver_type == "MILP"

    def test_study_event(self):
        """Test creating a study event."""
        event = create_study_event(
            event_type=EcoSystemiserEventType.STUDY_STARTED,
            study_id="study-101",
            source_agent="ecosystemiser",
            study_type="parametric",
            total_simulations=100
        )

        assert event.study_id == "study-101"
        assert event.study_type == "parametric"
        assert event.total_simulations == 100

    def test_ecosystemiser_event_integration(self):
        """Test that EcoSystemiser events work with the event bus."""
        bus = get_event_bus()
        received_events = []

        def handler(event):
            received_events.append(event)

        bus.subscribe(EcoSystemiserEventType.SIMULATION_COMPLETED, handler)

        # Create and publish a simulation event
        sim_event = create_simulation_event(
            event_type=EcoSystemiserEventType.SIMULATION_COMPLETED,
            simulation_id="sim-test",
            source_agent="test",
            results_path="/results/sim-test.json",
            duration_seconds=45.5
        )

        # Note: SimulationEvent inherits from our Event class
        # but has additional fields that need to be handled
        base_event = Event(
            event_type=sim_event.event_type,
            source_agent=sim_event.source_agent,
            correlation_id=sim_event.correlation_id,
            payload={
                "simulation_id": sim_event.simulation_id,
                "results_path": sim_event.results_path,
                "duration_seconds": sim_event.duration_seconds
            }
        )

        bus.publish(base_event)

        # Check event was received
        assert len(received_events) == 1
        received = received_events[0]
        assert received.event_type == EcoSystemiserEventType.SIMULATION_COMPLETED
        assert received.payload["simulation_id"] == "sim-test"
        assert received.payload["duration_seconds"] == 45.5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])