"""Event flow validation script.

Validates that events flow correctly through the unified event system.
Used for Phase B testing and validation.

Usage:
    python scripts/monitoring/validate_event_flow.py
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any
from uuid import uuid4

from hive_bus import (
    TopicRegistry,
    UnifiedEvent,
    UnifiedEventType,
    create_task_event,
    get_global_registry,
)
from hive_config import create_config_from_sources
from hive_logging import get_logger

logger = get_logger(__name__)


class EventFlowValidator:
    """Validate unified event flow."""

    def __init__(self):
        self.registry = get_global_registry()
        self.config = create_config_from_sources()
        self.received_events: list[UnifiedEvent] = []
        self.validation_results: dict[str, bool] = {}

    def setup_handlers(self) -> None:
        """Setup event handlers for validation."""

        def capture_event(event: UnifiedEvent) -> None:
            """Capture received events."""
            self.received_events.append(event)
            logger.info(f"Captured event: {event.event_type}")

        # Register handlers for all event patterns
        self.registry.register("task.*", capture_event)
        self.registry.register("review.*", capture_event)
        self.registry.register("workflow.*", capture_event)
        self.registry.register("deployment.*", capture_event)

    def emit_test_events(self) -> None:
        """Emit test events for validation."""
        correlation_id = str(uuid4())

        # Test task events
        task_created = create_task_event(
            event_type=UnifiedEventType.TASK_CREATED,
            task_id=str(uuid4()),
            correlation_id=correlation_id,
            source_agent="test-validator",
            additional_data={"test": "task_created"},
        )
        self.registry.emit(task_created)

        task_started = create_task_event(
            event_type=UnifiedEventType.TASK_STARTED,
            task_id=str(uuid4()),
            correlation_id=correlation_id,
            source_agent="test-validator",
            additional_data={"test": "task_started"},
        )
        self.registry.emit(task_started)

        # Test review events
        review_requested = UnifiedEvent(
            event_type=UnifiedEventType.REVIEW_REQUESTED,
            correlation_id=correlation_id,
            payload={"code_path": "/test/path"},
            source_agent="test-validator",
        )
        self.registry.emit(review_requested)

        # Test workflow events
        workflow_started = UnifiedEvent(
            event_type=UnifiedEventType.WORKFLOW_STARTED,
            correlation_id=correlation_id,
            payload={"workflow_type": "test"},
            source_agent="test-validator",
        )
        self.registry.emit(workflow_started)

        logger.info(f"Emitted 4 test events with correlation_id: {correlation_id}")

    def validate_pattern_matching(self) -> bool:
        """Validate topic pattern matching works correctly.

        Returns:
            True if validation passed
        """
        logger.info("Validating pattern matching...")

        # Count events by pattern
        task_events = [e for e in self.received_events if e.event_type.startswith("task.")]
        review_events = [
            e for e in self.received_events if e.event_type.startswith("review.")
        ]
        workflow_events = [
            e for e in self.received_events if e.event_type.startswith("workflow.")
        ]

        # Validate
        passed = True

        if len(task_events) != 2:
            logger.error(f"Expected 2 task events, got {len(task_events)}")
            passed = False

        if len(review_events) != 1:
            logger.error(f"Expected 1 review event, got {len(review_events)}")
            passed = False

        if len(workflow_events) != 1:
            logger.error(f"Expected 1 workflow event, got {len(workflow_events)}")
            passed = False

        self.validation_results["pattern_matching"] = passed
        return passed

    def validate_correlation_ids(self) -> bool:
        """Validate correlation IDs are preserved.

        Returns:
            True if validation passed
        """
        logger.info("Validating correlation IDs...")

        if not self.received_events:
            logger.error("No events received")
            return False

        # All events should have same correlation ID
        correlation_ids = {e.correlation_id for e in self.received_events}

        if len(correlation_ids) != 1:
            logger.error(
                f"Expected 1 correlation ID, got {len(correlation_ids)}: {correlation_ids}"
            )
            self.validation_results["correlation_ids"] = False
            return False

        logger.info(f"All events share correlation ID: {correlation_ids.pop()}")
        self.validation_results["correlation_ids"] = True
        return True

    def validate_event_structure(self) -> bool:
        """Validate event structure is correct.

        Returns:
            True if validation passed
        """
        logger.info("Validating event structure...")

        passed = True

        for event in self.received_events:
            # Check required fields
            if not event.event_type:
                logger.error(f"Event missing event_type: {event}")
                passed = False

            if not event.correlation_id:
                logger.error(f"Event missing correlation_id: {event}")
                passed = False

            if not event.source_agent:
                logger.error(f"Event missing source_agent: {event}")
                passed = False

            if not event.timestamp:
                logger.error(f"Event missing timestamp: {event}")
                passed = False

            # Validate timestamp type
            if not isinstance(event.timestamp, datetime):
                logger.error(f"Event timestamp not datetime: {type(event.timestamp)}")
                passed = False

            # Validate payload type
            if not isinstance(event.payload, dict):
                logger.error(f"Event payload not dict: {type(event.payload)}")
                passed = False

        self.validation_results["event_structure"] = passed
        return passed

    def validate_feature_flags(self) -> bool:
        """Validate feature flag configuration.

        Returns:
            True if validation passed
        """
        logger.info("Validating feature flag configuration...")

        passed = True

        # Check feature flags exist
        if not hasattr(self.config, "features"):
            logger.error("Config missing features attribute")
            passed = False
        else:
            # Check individual flags
            required_flags = [
                "enable_unified_events",
                "enable_dual_write",
                "enable_agent_adapters",
                "event_monitoring_enabled",
            ]

            for flag in required_flags:
                if not hasattr(self.config.features, flag):
                    logger.error(f"Feature flags missing: {flag}")
                    passed = False

            # Log current flag values
            logger.info(
                f"Feature flags: "
                f"unified_events={self.config.features.enable_unified_events}, "
                f"dual_write={self.config.features.enable_dual_write}, "
                f"agent_adapters={self.config.features.enable_agent_adapters}"
            )

        self.validation_results["feature_flags"] = passed
        return passed

    def run_validation(self) -> bool:
        """Run all validation checks.

        Returns:
            True if all validations passed
        """
        logger.info("Starting event flow validation...")

        # Setup
        self.setup_handlers()

        # Emit test events
        self.emit_test_events()

        # Wait for events to be processed
        import time

        time.sleep(1)

        # Run validations
        pattern_ok = self.validate_pattern_matching()
        correlation_ok = self.validate_correlation_ids()
        structure_ok = self.validate_event_structure()
        flags_ok = self.validate_feature_flags()

        # Print summary
        print("\n" + "=" * 80)
        print("EVENT FLOW VALIDATION SUMMARY")
        print("=" * 80)
        print(f"Pattern Matching:     {'PASS' if pattern_ok else 'FAIL'}")
        print(f"Correlation IDs:      {'PASS' if correlation_ok else 'FAIL'}")
        print(f"Event Structure:      {'PASS' if structure_ok else 'FAIL'}")
        print(f"Feature Flags:        {'PASS' if flags_ok else 'FAIL'}")
        print("-" * 80)

        all_passed = all([pattern_ok, correlation_ok, structure_ok, flags_ok])
        print(f"Overall Result:       {'PASS' if all_passed else 'FAIL'}")
        print("=" * 80 + "\n")

        return all_passed


def main():
    """Run event flow validation."""
    validator = EventFlowValidator()
    success = validator.run_validation()

    if success:
        logger.info("Event flow validation PASSED")
        exit(0)
    else:
        logger.error("Event flow validation FAILED")
        exit(1)


if __name__ == "__main__":
    main()
