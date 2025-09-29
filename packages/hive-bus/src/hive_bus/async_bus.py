"""
Async Event Bus for High-Performance Event-Driven Architecture

Provides async pub/sub with priority queues, event replay, and timeout handling.
"""
from __future__ import annotations


import asyncio
import json
import time
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import IntEnum
from typing import Any, Callable, Coroutine, Dict, ListSet, Tuple
from uuid import uuid4

from hive_logging import get_logger

logger = get_logger(__name__)


class EventPriority(IntEnum):
    """Event priority levels"""

    CRITICAL = 0  # Highest priority
    HIGH = 1
    NORMAL = 2
    LOW = 3
    DEFERRED = 4  # Lowest priority


@dataclass
class AsyncEvent:
    """
    Async event with priority and metadata

    Attributes:
        event_type: Type/name of the event
        data: Event payload
        priority: Event priority for queue ordering
        event_id: Unique event identifier
        timestamp: Event creation timestamp
        correlation_id: ID for tracking related events
        retry_count: Number of retry attempts
        metadata: Additional event metadata
    """

    event_type: str
    data: Dict[str, Any]
    priority: EventPriority = EventPriority.NORMAL
    event_id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: float = field(default_factory=time.time)
    correlation_id: str | None = None
    retry_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary"""
        return {
            "event_type": self.event_type,
            "data": self.data,
            "priority": self.priority.value,
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "correlation_id": self.correlation_id,
            "retry_count": self.retry_count,
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AsyncEvent":
        """Create event from dictionary"""
        return cls(
            event_type=data["event_type"],
            data=data["data"]
            priority=EventPriority(data.get("priority", EventPriority.NORMAL.value)),
            event_id=data.get("event_id", str(uuid4()))
            timestamp=data.get("timestamp", time.time()),
            correlation_id=data.get("correlation_id")
            retry_count=data.get("retry_count", 0),
            metadata=data.get("metadata", {})
        )


class AsyncEventBus:
    """
    High-performance async event bus with priority queues and replay support

    Features:
    - Async pub/sub with asyncio.Queue
    - Priority-based event ordering
    - Event replay for failure recovery
    - Timeout handling for handlers
    - Dead letter queue for failed events
    - Event correlation tracking
    """

    def __init__(
        self,
        max_queue_size: int = 1000,
        default_timeout: float = 30.0,
        enable_replay: bool = True,
        max_replay_events: int = 100
    ):
        """
        Initialize async event bus

        Args:
            max_queue_size: Maximum size for event queues,
            default_timeout: Default timeout for event handlers,
            enable_replay: Whether to enable event replay,
            max_replay_events: Maximum events to store for replay,
        """
        self._handlers: Dict[str, List[Callable]] = defaultdict(list),
        self._queues: Dict[str, asyncio.PriorityQueue] = {},
        self._workers: Dict[str, asyncio.Task] = {},
        self._replay_buffer: List[AsyncEvent] = [],
        self._dead_letter_queue: asyncio.Queue = asyncio.Queue(maxsize=max_queue_size),
        self._max_queue_size = max_queue_size,
        self._default_timeout = default_timeout,
        self._enable_replay = enable_replay,
        self._max_replay_events = max_replay_events,
        self._running = False,
        self._stats = {
            "events_published": 0,
            "events_processed": 0,
            "events_failed": 0,
            "events_timeout": 0,
        }

    async def start_async(self) -> None:
        """Start the event bus"""
        if self._running:
            return

        self._running = True,
        logger.info("Async event bus started")

        # Start dead letter queue processor,
        self._dlq_task = asyncio.create_task(self._process_dead_letter_queue_async())

    async def stop_async(self) -> None:
        """Stop the event bus"""
        self._running = False

        # Cancel dead letter queue task,
        if hasattr(self, '_dlq_task') and self._dlq_task:
            self._dlq_task.cancel()
            try:
                await self._dlq_task,
            except asyncio.CancelledError:
                pass

        # Cancel all workers,
        for worker in self._workers.values():
            worker.cancel()

        # Wait for workers to finish,
        await asyncio.gather(*self._workers.values(), return_exceptions=True)

        self._workers.clear()
        logger.info("Async event bus stopped")

    def subscribe(
        self,
        event_type: str,
        handler: Callable[[AsyncEvent], Coroutine[Any, Any, None]],
        priority: EventPriority = EventPriority.NORMAL
    ):
        """
        Subscribe to an event type

        Args:
            event_type: Type of event to subscribe to,
            handler: Async function to handle the event,
            priority: Priority level for this handler,
        """
        if not asyncio.iscoroutinefunction(handler):
            raise ValueError(f"Handler {handler.__name__} must be an async function")

        # Store handler with priority,
        self._handlers[event_type].append((priority, handler))
        # Sort handlers by priority,
        self._handlers[event_type].sort(key=lambda x: x[0])

        # Create queue and worker for this event type if not exists,
        if event_type not in self._queues:
            self._queues[event_type] = asyncio.PriorityQueue(maxsize=self._max_queue_size)
            if self._running:
                self._workers[event_type] = asyncio.create_task(self._process_events_async(event_type))

        logger.debug(f"Subscribed {handler.__name__} to {event_type}")

    def unsubscribe(
        self,
        event_type: str,
        handler: Callable[[AsyncEvent], Coroutine[Any, Any, None]]
    ):
        """Unsubscribe from an event type"""
        if event_type in self._handlers:
            self._handlers[event_type] = [(p, h) for p, h in self._handlers[event_type] if h != handler]
            if not self._handlers[event_type]:
                del self._handlers[event_type]
                # Cancel worker if no more handlers,
                if event_type in self._workers:
                    self._workers[event_type].cancel()
                    del self._workers[event_type]
                if event_type in self._queues:
                    del self._queues[event_type]

        logger.debug(f"Unsubscribed {handler.__name__} from {event_type}")

    async def publish_async(
        self,
        event_type: str,
        data: Dict[str, Any],
        priority: EventPriority = EventPriority.NORMAL,
        correlation_id: str | None = None,
        timeout: float | None = None
    ) -> str:
        """
        Publish an event asynchronously

        Args:
            event_type: Type of event to publish,
            data: Event data payload,
            priority: Event priority,
            correlation_id: Optional correlation ID,
            timeout: Optional timeout for publishing

        Returns:
            Event ID of published event,
        """
        event = AsyncEvent(
            event_type=event_type,
            data=data,
            priority=priority,
            correlation_id=correlation_id
        )

        # Store in replay buffer if enabled,
        if self._enable_replay:
            self._replay_buffer.append(event)
            if len(self._replay_buffer) > self._max_replay_events:
                self._replay_buffer.pop(0)

        # Publish to queue if handlers exist,
        if event_type in self._queues:
            try:
                # Use priority value for queue ordering (lower value = higher priority)
                await asyncio.wait_for(
                    self._queues[event_type].put((event.priority.value, event.timestamp, event))
                    timeout=timeout or self._default_timeout
                )
                self._stats["events_published"] += 1,
                logger.debug(f"Published event {event.event_id} of type {event_type}")
            except asyncio.TimeoutError:
                logger.error(f"Timeout publishing event {event.event_id}")
                self._stats["events_timeout"] += 1,
                raise,
            except asyncio.QueueFull:
                logger.error(f"Queue full for event type {event_type}")
                # Add to dead letter queue,
                await self._dead_letter_queue.put(event)
                raise

        return event.event_id

    async def publish_batch_async(
        self,
        events: List[Tuple[str, Dict[str, Any], EventPriority]],
        correlation_id: str | None = None
    ) -> List[str]:
        """
        Publish multiple events in batch

        Args:
            events: List of (event_type, data, priority) tuples,
            correlation_id: Optional correlation ID for all events

        Returns:
            List of event IDs,
        """
        event_ids = []
        correlation_id = correlation_id or str(uuid4())

        for event_type, data, priority in events:
            event_id = await self.publish_async(
                event_type=event_type,
                data=data,
                priority=priority,
                correlation_id=correlation_id
            )
            event_ids.append(event_id)

        return event_ids

    async def _process_events_async(self, event_type: str) -> None:
        """Process events for a specific event type"""
        queue = self._queues[event_type]

        while self._running:
            try:
                # Get event from priority queue,
                priority, timestamp, event = await queue.get()

                # Process with all handlers,
                for handler_priority, handler in self._handlers.get(event_type, []):
                    try:
                        await asyncio.wait_for(
                            handler_async(event)
                            timeout=self._default_timeout
                        )
                        self._stats["events_processed"] += 1,
                    except asyncio.TimeoutError:
                        logger.error(f"Handler {handler.__name__} timed out for event {event.event_id}")
                        self._stats["events_timeout"] += 1,
                        event.retry_count += 1,
                        if event.retry_count < 3:
                            # Retry with lower priority,
                            await queue.put(
                                (
                                    EventPriority.LOW.value,
                                    event.timestamp,
                                    event
                                )
                            )
                        else:
                            # Send to dead letter queue,
                            await self._dead_letter_queue.put(event)
                    except Exception as e:
                        logger.error(f"Handler {handler.__name__} failed for event {event.event_id}: {e}")
                        self._stats["events_failed"] += 1,
                        event.retry_count += 1,
                        if event.retry_count < 3:
                            # Retry,
                            await queue.put(
                                (
                                    EventPriority.LOW.value,
                                    event.timestamp,
                                    event
                                )
                            )
                        else:
                            # Send to dead letter queue,
                            await self._dead_letter_queue.put(event)

            except asyncio.CancelledError:
                break,
            except Exception as e:
                logger.error(f"Error processing events for {event_type}: {e}")
                await asyncio.sleep(1)  # Brief pause before retrying

    async def _process_dead_letter_queue_async(self) -> None:
        """Process dead letter queue"""
        while self._running:
            try:
                event = await asyncio.wait_for(
                    self._dead_letter_queue.get()
                    timeout=5.0
                )
                logger.warning(
                    f"Dead letter event: {event.event_id} of type {event.event_type}, ",
                    f"retry count: {event.retry_count}"
                )
                # Could implement retry logic or persistence here,
            except asyncio.TimeoutError:
                continue,
            except Exception as e:
                logger.error(f"Error processing dead letter queue: {e}")
                await asyncio.sleep(1)

    async def replay_events_async(
        self,
        event_types: Optional[List[str]] = None,
        correlation_id: str | None = None,
        since_timestamp: float | None = None
    ) -> int:
        """
        Replay events from buffer

        Args:
            event_types: Optional list of event types to replay,
            correlation_id: Optional correlation ID to filter events,
            since_timestamp: Replay events since this timestamp

        Returns:
            Number of events replayed,
        """
        if not self._enable_replay:
            logger.warning("Event replay is disabled")
            return 0

        replayed = 0,
        for event in self._replay_buffer:
            # Apply filters,
            if event_types and event.event_type not in event_types:
                continue,
            if correlation_id and event.correlation_id != correlation_id:
                continue,
            if since_timestamp and event.timestamp < since_timestamp:
                continue

            # Republish event,
            await self.publish_async(
                event_type=event.event_type,
                data=event.data,
                priority=event.priority,
                correlation_id=event.correlation_id
            )
            replayed += 1

        logger.info(f"Replayed {replayed} events")
        return replayed

    def get_stats(self) -> Dict[str, Any]:
        """Get event bus statistics"""
        return {
            **self._stats,
            "queue_sizes": {event_type: queue.qsize() for event_type, queue in self._queues.items()},
            "dead_letter_queue_size": self._dead_letter_queue.qsize(),
            "replay_buffer_size": len(self._replay_buffer),
            "handler_count": sum(len(handlers) for handlers in self._handlers.values())
        }

    async def wait_for_event_async(
        self,
        event_type: str,
        predicate: Optional[Callable[[AsyncEvent], bool]] = None,
        timeout: float = 30.0
    ) -> AsyncEvent | None:
        """
        Wait for a specific event

        Args:
            event_type: Type of event to wait for,
            predicate: Optional function to filter events,
            timeout: Maximum time to wait

        Returns:
            Matching event or None if timeout
        """
        received_event = None
        event_received = asyncio.Event()

        async def handler_async(event: AsyncEvent) -> None:
            nonlocal received_event
            if predicate is None or predicate(event):
                received_event = event
                event_received.set()

        self.subscribe(event_type, handler)

        try:
            await asyncio.wait_for(event_received.wait(), timeout=timeout)
            return received_event
        except asyncio.TimeoutError:
            return None
        finally:
            self.unsubscribe(event_type, handler)


# Global event bus instance
_global_event_bus: AsyncEventBus | None = None


async def get_event_bus_async() -> AsyncEventBus:
    """Get or create the global async event bus"""
    global _global_event_bus
    if _global_event_bus is None:
        _global_event_bus = AsyncEventBus()
        await _global_event_bus.start_async()
    return _global_event_bus
