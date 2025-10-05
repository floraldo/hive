"""Dual-write consistency validation script.

Validates that data is correctly written to both legacy and unified schemas
during Phase C dual-write operations.

Usage:
    python scripts/monitoring/validate_dual_write_consistency.py [--task-id TASK_ID]
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime
from typing import Any

from hive_orchestration.database import create_dual_write_repository

from hive_config import create_config_from_sources
from hive_logging import get_logger

logger = get_logger(__name__)


class DualWriteConsistencyValidator:
    """Validate consistency between legacy and unified schemas."""

    def __init__(self):
        self.config = create_config_from_sources()
        self.validation_results: list[dict[str, Any]] = []

    async def validate_task(self, task_id: str) -> dict[str, Any]:
        """Validate consistency for a specific task.

        Args:
            task_id: Task to validate

        Returns:
            Validation result
        """
        logger.info(f"Validating task: {task_id}")

        result = {
            "task_id": task_id,
            "timestamp": datetime.utcnow(),
            "consistent": True,
            "discrepancies": [],
        }

        try:
            # Get dual-write repository
            repository = await create_dual_write_repository(enable_legacy=True)

            # Get task from unified schema
            unified_task = await repository.get_task(task_id)

            if unified_task is None:
                result["consistent"] = False
                result["discrepancies"].append(f"Task {task_id} not found in unified schema")
                return result

            # TODO: Compare with legacy schema
            # This would require reading from legacy database
            # For now, just validate unified schema has required fields

            required_fields = ["id", "correlation_id", "task_type", "status", "agent_type"]
            for field in required_fields:
                if not hasattr(unified_task, field):
                    result["consistent"] = False
                    result["discrepancies"].append(f"Missing field: {field}")

            # Validate data types
            if not isinstance(unified_task.input_data, dict):
                result["consistent"] = False
                result["discrepancies"].append("input_data is not a dict")

            if not isinstance(unified_task.correlation_id, str):
                result["consistent"] = False
                result["discrepancies"].append("correlation_id is not a string")

            logger.info(f"Task {task_id} validation: {'PASS' if result['consistent'] else 'FAIL'}")

        except Exception as e:
            logger.error(f"Validation error for task {task_id}: {e}")
            result["consistent"] = False
            result["discrepancies"].append(f"Exception: {str(e)}")

        self.validation_results.append(result)
        return result

    async def validate_all_tasks(self, limit: int = 100) -> list[dict[str, Any]]:
        """Validate consistency for all recent tasks.

        Args:
            limit: Maximum number of tasks to validate

        Returns:
            List of validation results
        """
        logger.info(f"Validating up to {limit} recent tasks...")

        try:
            # Get dual-write repository
            repository = await create_dual_write_repository(enable_legacy=True)

            # TODO: Get list of recent task IDs from database
            # For now, this is a placeholder

            task_ids = []  # Replace with actual query

            if not task_ids:
                logger.warning("No tasks found to validate")
                return []

            for task_id in task_ids[:limit]:
                await self.validate_task(task_id)

        except Exception as e:
            logger.error(f"Batch validation failed: {e}")

        return self.validation_results

    def print_summary(self) -> None:
        """Print validation summary."""
        if not self.validation_results:
            print("No validation results to display")
            return

        total = len(self.validation_results)
        consistent = sum(1 for r in self.validation_results if r["consistent"])
        inconsistent = total - consistent

        print("\n" + "=" * 80)
        print("DUAL-WRITE CONSISTENCY VALIDATION SUMMARY")
        print("=" * 80)
        print(f"Total Tasks Validated:   {total}")
        print(f"Consistent:              {consistent} ({consistent/total*100:.1f}%)")
        print(f"Inconsistent:            {inconsistent} ({inconsistent/total*100:.1f}%)")

        if inconsistent > 0:
            print("\nInconsistent Tasks:")
            print("-" * 80)
            for result in self.validation_results:
                if not result["consistent"]:
                    print(f"\nTask ID: {result['task_id']}")
                    print(f"  Timestamp: {result['timestamp']}")
                    print("  Discrepancies:")
                    for discrepancy in result["discrepancies"]:
                        print(f"    - {discrepancy}")

        print("=" * 80 + "\n")

    def get_consistency_rate(self) -> float:
        """Calculate consistency rate.

        Returns:
            Percentage of consistent tasks (0-100)
        """
        if not self.validation_results:
            return 0.0

        consistent = sum(1 for r in self.validation_results if r["consistent"])
        return (consistent / len(self.validation_results)) * 100


async def main():
    """Run dual-write consistency validation."""
    parser = argparse.ArgumentParser(description="Validate dual-write consistency")
    parser.add_argument("--task-id", type=str, help="Validate specific task ID")
    parser.add_argument("--limit", type=int, default=100, help="Max tasks to validate")

    args = parser.parse_args()

    # Check if dual-write is enabled
    config = create_config_from_sources()
    if not config.features.enable_dual_write:
        print("ERROR: Dual-write is not enabled in configuration")
        print("Set features.enable_dual_write=true in hive_config.json")
        return 1

    if not config.features.dual_write_validate:
        print("WARNING: Dual-write validation is disabled in configuration")
        print("Proceeding anyway, but consider enabling features.dual_write_validate=true")

    validator = DualWriteConsistencyValidator()

    if args.task_id:
        # Validate specific task
        result = await validator.validate_task(args.task_id)
        print(f"\nTask {args.task_id}: {'CONSISTENT' if result['consistent'] else 'INCONSISTENT'}")

        if not result["consistent"]:
            print("\nDiscrepancies:")
            for discrepancy in result["discrepancies"]:
                print(f"  - {discrepancy}")
    else:
        # Validate all recent tasks
        await validator.validate_all_tasks(limit=args.limit)

    validator.print_summary()

    # Return exit code based on consistency
    consistency_rate = validator.get_consistency_rate()
    if consistency_rate < 100:
        logger.warning(f"Consistency rate: {consistency_rate:.1f}% - some discrepancies found")
        return 1

    logger.info(f"Consistency rate: {consistency_rate:.1f}% - all checks passed")
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
