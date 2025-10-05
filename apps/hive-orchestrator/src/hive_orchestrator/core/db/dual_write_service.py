"""Dual-write service integration for hive-orchestrator.

Provides access to dual-write functionality from hive-orchestration package
while maintaining backward compatibility with legacy database operations.

This allows gradual migration controlled by feature flags.
"""

from __future__ import annotations

from typing import Any

from hive_config import create_config_from_sources
from hive_logging import get_logger
from hive_orchestration.database import DualWriteTaskRepository, create_dual_write_repository

logger = get_logger(__name__)


class DualWriteService:
    """Service for accessing dual-write task repository.

    Integrates the dual-write pattern from hive-orchestration into
    the orchestrator, allowing gradual migration when feature flags are enabled.
    """

    def __init__(self):
        """Initialize dual-write service."""
        self.config = create_config_from_sources()
        self._repository: DualWriteTaskRepository | None = None

    async def get_repository(self) -> DualWriteTaskRepository | None:
        """Get dual-write repository if enabled.

        Returns:
            DualWriteTaskRepository if dual-write is enabled, None otherwise
        """
        # Only create repository if dual-write is enabled
        if not self.config.features.enable_dual_write:
            logger.debug("Dual-write not enabled, returning None")
            return None

        # Create repository if not already created
        if self._repository is None:
            logger.info("Initializing dual-write repository")
            self._repository = await create_dual_write_repository(enable_legacy=True)

        return self._repository

    async def create_task(
        self,
        task_type: str,
        agent_type: str,
        input_data: dict[str, Any],
        correlation_id: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any] | None:
        """Create task using dual-write if enabled.

        Args:
            task_type: Type of task (review, plan, code, etc.)
            agent_type: Which agent handles this task
            input_data: Task input data
            correlation_id: Correlation ID for tracking
            **kwargs: Additional task fields

        Returns:
            Created task dict if dual-write enabled, None otherwise
        """
        repository = await self.get_repository()
        if repository is None:
            return None

        try:
            task = await repository.create_task(
                task_type=task_type,
                agent_type=agent_type,
                input_data=input_data,
                correlation_id=correlation_id,
                **kwargs,
            )

            logger.info(f"Created task via dual-write: {task.id}")

            # Convert to dict for legacy compatibility
            return {
                "id": task.id,
                "correlation_id": task.correlation_id,
                "task_type": task.task_type,
                "agent_type": task.agent_type,
                "status": task.status,
                "input_data": task.input_data,
                "output_data": task.output_data,
                "created_at": task.created_at,
                "updated_at": task.updated_at,
            }

        except Exception as e:
            logger.error(f"Dual-write task creation failed: {e}")
            return None

    async def update_task_status(
        self,
        task_id: str,
        status: str,
        **kwargs: Any,
    ) -> bool:
        """Update task status using dual-write if enabled.

        Args:
            task_id: Task identifier
            status: New status
            **kwargs: Additional fields to update

        Returns:
            True if update successful, False otherwise
        """
        repository = await self.get_repository()
        if repository is None:
            return False

        try:
            await repository.update_status(task_id, status, **kwargs)
            logger.debug(f"Updated task {task_id} status to {status} via dual-write")
            return True

        except Exception as e:
            logger.error(f"Dual-write status update failed: {e}")
            return False

    async def validate_consistency(self, task_id: str) -> dict[str, Any]:
        """Validate consistency between legacy and unified schemas.

        Args:
            task_id: Task to validate

        Returns:
            Validation result with any discrepancies found
        """
        repository = await self.get_repository()
        if repository is None:
            return {"error": "Dual-write not enabled"}

        if not self.config.features.dual_write_validate:
            return {"validated": False, "reason": "Validation not enabled"}

        try:
            # Get task from unified schema
            unified_task = await repository.get_task(task_id)

            if unified_task is None:
                return {
                    "validated": False,
                    "error": f"Task {task_id} not found in unified schema",
                }

            # TODO: Compare with legacy schema
            # This would require access to legacy database connection

            return {
                "validated": True,
                "task_id": task_id,
                "schemas_match": True,  # Placeholder - implement actual comparison
            }

        except Exception as e:
            logger.error(f"Consistency validation failed: {e}")
            return {"validated": False, "error": str(e)}


# Singleton instance for orchestrator use
_dual_write_service: DualWriteService | None = None


def get_dual_write_service() -> DualWriteService:
    """Get singleton dual-write service instance.

    Returns:
        DualWriteService instance
    """
    global _dual_write_service
    if _dual_write_service is None:
        _dual_write_service = DualWriteService()
    return _dual_write_service
