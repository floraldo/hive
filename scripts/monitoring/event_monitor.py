"""Event flow monitoring utility for Phase B validation.

This script monitors unified event flow for debugging and metrics collection.
Used to validate event emission during gradual rollout.

Usage:
    python scripts/monitoring/event_monitor.py
"""

from __future__ import annotations

import time
from collections import defaultdict
from datetime import datetime
from typing import Any

from hive_bus import TopicRegistry, UnifiedEvent, get_global_registry
from hive_config import create_config_from_sources
from hive_logging import get_logger

logger = get_logger(__name__)


class EventMetrics:
    """Track event flow metrics."""

    def __init__(self):
        self.event_counts: dict[str, int] = defaultdict(int)
        self.event_timestamps: list[tuple[datetime, str]] = []
        self.event_latencies: list[float] = []
        self.processing_errors: list[dict[str, Any]] = []
        self.start_time = datetime.utcnow()

    def record_event(self, event: UnifiedEvent) -> None:
        """Record event occurrence."""
        self.event_counts[event.event_type] += 1
        self.event_timestamps.append((datetime.utcnow(), event.event_type))

        # Calculate latency if event has timestamp
        if event.timestamp:
            latency = (datetime.utcnow() - event.timestamp).total_seconds()
            self.event_latencies.append(latency)

    def record_error(self, event: UnifiedEvent, error: Exception) -> None:
        """Record event processing error."""
        self.processing_errors.append(
            {
                "event_type": event.event_type,
                "correlation_id": event.correlation_id,
                "error": str(error),
                "timestamp": datetime.utcnow(),
            }
        )

    def get_events_per_minute(self) -> float:
        """Calculate events per minute."""
        runtime = (datetime.utcnow() - self.start_time).total_seconds() / 60
        total_events = sum(self.event_counts.values())
        return total_events / runtime if runtime > 0 else 0

    def get_average_latency(self) -> float:
        """Calculate average event latency in seconds."""
        if not self.event_latencies:
            return 0.0
        return sum(self.event_latencies) / len(self.event_latencies)

    def get_summary(self) -> dict[str, Any]:
        """Get metrics summary."""
        return {
            "total_events": sum(self.event_counts.values()),
            "events_by_type": dict(self.event_counts),
            "events_per_minute": round(self.get_events_per_minute(), 2),
            "average_latency_ms": round(self.get_average_latency() * 1000, 2),
            "processing_errors": len(self.processing_errors),
            "runtime_minutes": round(
                (datetime.utcnow() - self.start_time).total_seconds() / 60, 2
            ),
        }


class EventMonitor:
    """Monitor unified event flow for debugging and validation."""

    def __init__(
        self,
        registry: TopicRegistry | None = None,
        verbose: bool = True,
    ):
        """Initialize event monitor.

        Args:
            registry: Topic registry to monitor (defaults to global)
            verbose: Whether to print events to console
        """
        self.registry = registry or get_global_registry()
        self.verbose = verbose
        self.metrics = EventMetrics()
        self.config = create_config_from_sources()

    def start(self) -> None:
        """Start monitoring all events."""
        # Register for all events
        self.registry.register("*", self._log_event)

        logger.info("Event monitor started - listening for all events")
        logger.info(
            f"Event monitoring enabled: {self.config.features.event_monitoring_enabled}"
        )
        logger.info(
            f"Unified events enabled: {self.config.features.enable_unified_events}"
        )

    def _log_event(self, event: UnifiedEvent) -> None:
        """Log event details and update metrics.

        Args:
            event: Unified event to log
        """
        try:
            # Update metrics
            self.metrics.record_event(event)

            # Log to console if verbose
            if self.verbose:
                self._print_event(event)

            # Log to file
            logger.debug(
                f"Event: {event.event_type} | "
                f"Correlation: {event.correlation_id} | "
                f"Source: {event.source_agent} | "
                f"Timestamp: {event.timestamp}"
            )

        except Exception as e:
            logger.error(f"Error processing event: {e}")
            self.metrics.record_error(event, e)

    def _print_event(self, event: UnifiedEvent) -> None:
        """Print event to console.

        Args:
            event: Event to print
        """
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(
            f"[{timestamp}] {event.event_type:30} | "
            f"Correlation: {event.correlation_id:20} | "
            f"Source: {event.source_agent}"
        )

        # Print payload if present
        if event.payload:
            print(f"         Payload: {event.payload}")

    def print_summary(self) -> None:
        """Print metrics summary."""
        summary = self.metrics.get_summary()

        print("\n" + "=" * 80)
        print("EVENT MONITORING SUMMARY")
        print("=" * 80)
        print(f"Total Events:        {summary['total_events']}")
        print(f"Events per Minute:   {summary['events_per_minute']}")
        print(f"Average Latency:     {summary['average_latency_ms']} ms")
        print(f"Processing Errors:   {summary['processing_errors']}")
        print(f"Runtime:             {summary['runtime_minutes']} minutes")
        print("\nEvents by Type:")
        print("-" * 80)

        for event_type, count in sorted(
            summary["events_by_type"].items(), key=lambda x: x[1], reverse=True
        ):
            print(f"  {event_type:40} {count:6} events")

        if self.metrics.processing_errors:
            print("\nProcessing Errors:")
            print("-" * 80)
            for error in self.metrics.processing_errors[-5:]:  # Last 5 errors
                print(
                    f"  {error['timestamp'].strftime('%H:%M:%S')} | "
                    f"{error['event_type']:30} | {error['error']}"
                )

        print("=" * 80 + "\n")

    def get_metrics(self) -> dict[str, Any]:
        """Get current metrics.

        Returns:
            Metrics dictionary
        """
        return self.metrics.get_summary()


def main():
    """Run event monitor."""
    print("Starting event monitor...")
    print("Press Ctrl+C to stop and see summary\n")

    monitor = EventMonitor(verbose=True)
    monitor.start()

    try:
        while True:
            time.sleep(60)  # Print summary every minute
            monitor.print_summary()
    except KeyboardInterrupt:
        print("\nStopping monitor...")
        monitor.print_summary()


if __name__ == "__main__":
    main()
