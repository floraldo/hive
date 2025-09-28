"""
EcoSystemiser Event Bus - Inherited and Extended from Hive Event Bus.

This module provides EcoSystemiser-specific event bus capabilities that inherit
from the base Hive event bus while adding domain-specific features for
climate and energy system simulation workflows.

Follows the "Inherit and Extend" pattern for true Hive native integration.
"""

from typing import Dict, Any, Optional, List, Callable, Awaitable
from datetime import datetime
import asyncio

# Temporary: Create minimal stubs for missing hive_bus dependency
try:
    from hive_bus import EventBus as HiveEventBus, Event
except ImportError:
    # Fallback: Define minimal stubs for testing
    class Event:
        """Minimal Event stub"""
        def __init__(self, type: str, data: Any):
            self.type = type
            self.data = data
            self.timestamp = datetime.now()

    class HiveEventBus:
        """Minimal EventBus stub"""
        def __init__(self):
            self.handlers = {}

        async def emit(self, event: Event):
            pass

        def on(self, event_type: str, handler: Callable):
            pass
from EcoSystemiser.hive_logging_adapter import get_logger
from EcoSystemiser.events import (
    EcoSystemiserEventType,
    SimulationEvent,
    StudyEvent,
    AnalysisEvent,
    OptimizationEvent
)

logger = get_logger(__name__)


class EcoSystemiserEventBus(HiveEventBus):
    """
    EcoSystemiser-specific event bus extending Hive Event Bus.

    Adds domain-specific event handling, filtering, and routing capabilities
    for climate and energy system simulation workflows while maintaining
    full compatibility with the base Hive event system.
    """

    def __init__(self, **kwargs):
        """Initialize EcoSystemiser Event Bus.

        Args:
            **kwargs: Additional arguments passed to HiveEventBus
        """
        super().__init__(**kwargs)
        self._simulation_events: Dict[str, List[Event]] = {}
        self._study_events: Dict[str, List[Event]] = {}
        self._analysis_events: Dict[str, List[Event]] = {}
        self._event_metrics = {
            'simulations_started': 0,
            'simulations_completed': 0,
            'simulations_failed': 0,
            'studies_started': 0,
            'studies_completed': 0,
            'studies_failed': 0,
            'analyses_started': 0,
            'analyses_completed': 0,
            'analyses_failed': 0
        }

    async def publish_simulation_event(self, event: SimulationEvent) -> None:
        """Publish simulation-specific event with enhanced tracking.

        Args:
            event: Simulation event to publish
        """
        # Track simulation events by simulation_id
        simulation_id = event.simulation_id
        if simulation_id not in self._simulation_events:
            self._simulation_events[simulation_id] = []
        self._simulation_events[simulation_id].append(event)

        # Update metrics
        if event.event_type == EcoSystemiserEventType.SIMULATION_STARTED:
            self._event_metrics['simulations_started'] += 1
        elif event.event_type == EcoSystemiserEventType.SIMULATION_COMPLETED:
            self._event_metrics['simulations_completed'] += 1
        elif event.event_type == EcoSystemiserEventType.SIMULATION_FAILED:
            self._event_metrics['simulations_failed'] += 1

        # Publish to base event bus
        await self.publish(event)
        logger.debug(f"Published simulation event: {event.event_type} for {simulation_id}")

    async def publish_study_event(self, event: StudyEvent) -> None:
        """Publish study-specific event with enhanced tracking.

        Args:
            event: Study event to publish
        """
        # Track study events by study_id
        study_id = event.study_id
        if study_id not in self._study_events:
            self._study_events[study_id] = []
        self._study_events[study_id].append(event)

        # Update metrics
        if event.event_type == EcoSystemiserEventType.STUDY_STARTED:
            self._event_metrics['studies_started'] += 1
        elif event.event_type == EcoSystemiserEventType.STUDY_COMPLETED:
            self._event_metrics['studies_completed'] += 1
        elif event.event_type == EcoSystemiserEventType.STUDY_FAILED:
            self._event_metrics['studies_failed'] += 1

        # Publish to base event bus
        await self.publish(event)
        logger.debug(f"Published study event: {event.event_type} for {study_id}")

    async def publish_analysis_event(self, event: AnalysisEvent) -> None:
        """Publish analysis-specific event with enhanced tracking.

        Args:
            event: Analysis event to publish
        """
        # Track analysis events by analysis_id
        analysis_id = event.analysis_id
        if analysis_id not in self._analysis_events:
            self._analysis_events[analysis_id] = []
        self._analysis_events[analysis_id].append(event)

        # Update metrics
        if event.event_type == EcoSystemiserEventType.ANALYSIS_STARTED:
            self._event_metrics['analyses_started'] += 1
        elif event.event_type == EcoSystemiserEventType.ANALYSIS_COMPLETED:
            self._event_metrics['analyses_completed'] += 1
        elif event.event_type == EcoSystemiserEventType.ANALYSIS_FAILED:
            self._event_metrics['analyses_failed'] += 1

        # Publish to base event bus
        await self.publish(event)
        logger.debug(f"Published analysis event: {event.event_type} for {analysis_id}")

    async def subscribe_to_simulation_lifecycle(self,
                                              handler: Callable[[SimulationEvent], Awaitable[None]],
                                              simulation_id: Optional[str] = None) -> List[str]:
        """Subscribe to all simulation lifecycle events.

        Args:
            handler: Event handler function
            simulation_id: Optional specific simulation ID to filter

        Returns:
            List of subscription IDs for unsubscribing
        """
        subscription_ids = []

        # Create wrapper that filters by simulation_id if specified
        async def filtered_handler(event: Event) -> None:
            if isinstance(event, SimulationEvent):
                if simulation_id is None or event.simulation_id == simulation_id:
                    await handler(event)

        # Subscribe to all simulation event types
        for event_type in [
            EcoSystemiserEventType.SIMULATION_STARTED,
            EcoSystemiserEventType.SIMULATION_COMPLETED,
            EcoSystemiserEventType.SIMULATION_FAILED
        ]:
            sub_id = await self.subscribe(event_type, filtered_handler)
            subscription_ids.append(sub_id)

        logger.info(f"Subscribed to simulation lifecycle events (filter: {simulation_id})")
        return subscription_ids

    async def subscribe_to_study_lifecycle(self,
                                         handler: Callable[[StudyEvent], Awaitable[None]],
                                         study_id: Optional[str] = None) -> List[str]:
        """Subscribe to all study lifecycle events.

        Args:
            handler: Event handler function
            study_id: Optional specific study ID to filter

        Returns:
            List of subscription IDs for unsubscribing
        """
        subscription_ids = []

        async def filtered_handler(event: Event) -> None:
            if isinstance(event, StudyEvent):
                if study_id is None or event.study_id == study_id:
                    await handler(event)

        for event_type in [
            EcoSystemiserEventType.STUDY_STARTED,
            EcoSystemiserEventType.STUDY_COMPLETED,
            EcoSystemiserEventType.STUDY_FAILED
        ]:
            sub_id = await self.subscribe(event_type, filtered_handler)
            subscription_ids.append(sub_id)

        logger.info(f"Subscribed to study lifecycle events (filter: {study_id})")
        return subscription_ids

    async def subscribe_to_analysis_lifecycle(self,
                                            handler: Callable[[AnalysisEvent], Awaitable[None]],
                                            analysis_id: Optional[str] = None) -> List[str]:
        """Subscribe to all analysis lifecycle events.

        Args:
            handler: Event handler function
            analysis_id: Optional specific analysis ID to filter

        Returns:
            List of subscription IDs for unsubscribing
        """
        subscription_ids = []

        async def filtered_handler(event: Event) -> None:
            if isinstance(event, AnalysisEvent):
                if analysis_id is None or event.analysis_id == analysis_id:
                    await handler(event)

        for event_type in [
            EcoSystemiserEventType.ANALYSIS_STARTED,
            EcoSystemiserEventType.ANALYSIS_COMPLETED,
            EcoSystemiserEventType.ANALYSIS_FAILED
        ]:
            sub_id = await self.subscribe(event_type, filtered_handler)
            subscription_ids.append(sub_id)

        logger.info(f"Subscribed to analysis lifecycle events (filter: {analysis_id})")
        return subscription_ids

    def get_simulation_history(self, simulation_id: str) -> List[Event]:
        """Get event history for a specific simulation.

        Args:
            simulation_id: Simulation identifier

        Returns:
            List of events for the simulation
        """
        return self._simulation_events.get(simulation_id, [])

    def get_study_history(self, study_id: str) -> List[Event]:
        """Get event history for a specific study.

        Args:
            study_id: Study identifier

        Returns:
            List of events for the study
        """
        return self._study_events.get(study_id, [])

    def get_analysis_history(self, analysis_id: str) -> List[Event]:
        """Get event history for a specific analysis.

        Args:
            analysis_id: Analysis identifier

        Returns:
            List of events for the analysis
        """
        return self._analysis_events.get(analysis_id, [])

    def get_metrics(self) -> Dict[str, Any]:
        """Get current event metrics and statistics.

        Returns:
            Dictionary with event metrics
        """
        return {
            **self._event_metrics,
            'active_simulations': len(self._simulation_events),
            'active_studies': len(self._study_events),
            'active_analyses': len(self._analysis_events),
            'success_rates': {
                'simulations': (
                    self._event_metrics['simulations_completed'] /
                    max(1, self._event_metrics['simulations_started'])
                ) * 100,
                'studies': (
                    self._event_metrics['studies_completed'] /
                    max(1, self._event_metrics['studies_started'])
                ) * 100,
                'analyses': (
                    self._event_metrics['analyses_completed'] /
                    max(1, self._event_metrics['analyses_started'])
                ) * 100
            }
        }

    async def wait_for_simulation_completion(self,
                                           simulation_id: str,
                                           timeout: Optional[float] = None) -> bool:
        """Wait for a specific simulation to complete.

        Args:
            simulation_id: Simulation to wait for
            timeout: Maximum time to wait in seconds

        Returns:
            True if simulation completed, False if failed or timed out
        """
        completion_event = asyncio.Event()
        simulation_success = False

        async def completion_handler(event: SimulationEvent):
            nonlocal simulation_success
            if event.simulation_id == simulation_id:
                if event.event_type == EcoSystemiserEventType.SIMULATION_COMPLETED:
                    simulation_success = True
                completion_event.set()

        # Subscribe to simulation events
        subscription_ids = await self.subscribe_to_simulation_lifecycle(
            completion_handler, simulation_id
        )

        try:
            # Wait for completion or timeout
            await asyncio.wait_for(completion_event.wait(), timeout)
            return simulation_success
        except asyncio.TimeoutError:
            logger.warning(f"Timeout waiting for simulation {simulation_id}")
            return False
        finally:
            # Unsubscribe
            for sub_id in subscription_ids:
                await self.unsubscribe(sub_id)

    async def wait_for_study_completion(self,
                                      study_id: str,
                                      timeout: Optional[float] = None) -> bool:
        """Wait for a specific study to complete.

        Args:
            study_id: Study to wait for
            timeout: Maximum time to wait in seconds

        Returns:
            True if study completed, False if failed or timed out
        """
        completion_event = asyncio.Event()
        study_success = False

        async def completion_handler(event: StudyEvent):
            nonlocal study_success
            if event.study_id == study_id:
                if event.event_type == EcoSystemiserEventType.STUDY_COMPLETED:
                    study_success = True
                completion_event.set()

        subscription_ids = await self.subscribe_to_study_lifecycle(
            completion_handler, study_id
        )

        try:
            await asyncio.wait_for(completion_event.wait(), timeout)
            return study_success
        except asyncio.TimeoutError:
            logger.warning(f"Timeout waiting for study {study_id}")
            return False
        finally:
            for sub_id in subscription_ids:
                await self.unsubscribe(sub_id)

    def clear_history(self, older_than: Optional[datetime] = None):
        """Clear event history to manage memory usage.

        Args:
            older_than: Optional datetime to clear events before
        """
        if older_than is None:
            # Clear all history
            self._simulation_events.clear()
            self._study_events.clear()
            self._analysis_events.clear()
            logger.info("Cleared all event history")
        else:
            # Clear events older than specified time
            # This would require adding timestamps to events
            # Implementation depends on specific requirements
            logger.info(f"Cleared event history older than {older_than}")


# Global instance for application use
ecosystemiser_event_bus = EcoSystemiserEventBus()


class SyncEventPublisher:
    """
    Synchronous wrapper for event publishing from sync contexts.

    Provides fire-and-forget event publishing for sync methods that need
    to publish events without blocking or requiring async context.
    """

    def __init__(self, event_bus: EcoSystemiserEventBus):
        """Initialize sync publisher.

        Args:
            event_bus: EcoSystemiser event bus to wrap
        """
        self.event_bus = event_bus

    def try_publish_study_event(self, event) -> bool:
        """Try to publish study event in sync context.

        Args:
            event: Study event to publish

        Returns:
            True if published successfully, False otherwise
        """
        import asyncio

        try:
            # Try to get current event loop
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # We're in an async context - schedule the coroutine
                asyncio.create_task(self.event_bus.publish_study_event(event))
                return True
            else:
                # No running loop - run in new loop
                loop.run_until_complete(self.event_bus.publish_study_event(event))
                return True
        except RuntimeError:
            # No event loop available - try to create one
            try:
                asyncio.run(self.event_bus.publish_study_event(event))
                return True
            except Exception as e:
                logger.debug(f"Failed to publish study event in sync context: {e}")
                return False
        except Exception as e:
            logger.warning(f"Failed to publish study event: {e}")
            return False

    def try_publish_analysis_event(self, event) -> bool:
        """Try to publish analysis event in sync context.

        Args:
            event: Analysis event to publish

        Returns:
            True if published successfully, False otherwise
        """
        import asyncio

        try:
            # Try to get current event loop
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # We're in an async context - schedule the coroutine
                asyncio.create_task(self.event_bus.publish_analysis_event(event))
                return True
            else:
                # No running loop - run in new loop
                loop.run_until_complete(self.event_bus.publish_analysis_event(event))
                return True
        except RuntimeError:
            # No event loop available - try to create one
            try:
                asyncio.run(self.event_bus.publish_analysis_event(event))
                return True
            except Exception as e:
                logger.debug(f"Failed to publish analysis event in sync context: {e}")
                return False
        except Exception as e:
            logger.warning(f"Failed to publish analysis event: {e}")
            return False


# Global sync publisher for application use
sync_event_publisher = SyncEventPublisher(ecosystemiser_event_bus)