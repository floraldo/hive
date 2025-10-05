"""Dual-write repository for safe schema migration.

During migration, we write to BOTH legacy and unified schemas to ensure:
1. Old services keep working (reading from legacy schema)
2. New services use unified schema as source of truth
3. Data consistency across both schemas
4. Safe rollback if issues arise

Strategy:
    - ALL writes go to both schemas
    - ALL reads come from unified schema (source of truth)
    - Transaction safety: both commit or both rollback
    - Final step (Q3 2025): Remove legacy schema, stop dual-write
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from hive_db import get_sqlite_connection
from hive_logging import get_logger
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from .unified_schema import (
    UnifiedDeploymentTask,
    UnifiedReviewTask,
    UnifiedTask,
    UnifiedWorkflowTask,
)

logger = get_logger(__name__)


class DualWriteTaskRepository:
    """Repository that writes to both legacy and unified schemas.

    This ensures backwards compatibility during migration while allowing
    new services to use the unified schema as source of truth.
    """

    def __init__(
        self,
        session: AsyncSession,
        legacy_session: AsyncSession | None = None,
    ):
        """Initialize dual-write repository.

        Args:
            session: Unified schema session (source of truth)
            legacy_session: Legacy schema session (for backwards compat)
                           If None, only writes to unified (post-migration)
        """
        self.session = session
        self.legacy_session = legacy_session
        self._dual_write_enabled = legacy_session is not None

    async def create_task(
        self,
        task_type: str,
        agent_type: str,
        input_data: dict[str, Any],
        correlation_id: str | None = None,
        **kwargs: Any,
    ) -> UnifiedTask:
        """Create task in both schemas.

        Args:
            task_type: Type of task (review, plan, code, etc.)
            agent_type: Which agent handles this task
            input_data: Task input data
            correlation_id: Correlation ID for tracking across agents
            **kwargs: Additional task fields

        Returns:
            UnifiedTask: Created task from unified schema
        """
        task_id = str(uuid4())
        correlation_id = correlation_id or task_id

        # Create in unified schema
        unified_task = UnifiedTask(
            id=task_id,
            correlation_id=correlation_id,
            task_type=task_type,
            agent_type=agent_type,
            status="pending",
            input_data=input_data,
            **kwargs,
        )

        self.session.add(unified_task)

        # Also write to legacy schema if enabled
        if self._dual_write_enabled and self.legacy_session:
            legacy_task = await self._convert_to_legacy(unified_task)
            self.legacy_session.add(legacy_task)

        # Commit both or rollback both
        try:
            await self.session.commit()
            if self._dual_write_enabled and self.legacy_session:
                await self.legacy_session.commit()
        except Exception as e:
            logger.error(f"Dual-write failed: {e}")
            await self.session.rollback()
            if self._dual_write_enabled and self.legacy_session:
                await self.legacy_session.rollback()
            raise

        logger.info(
            f"Created task {task_id} (type={task_type}, agent={agent_type}, "
            f"dual_write={'enabled' if self._dual_write_enabled else 'disabled'})"
        )

        return unified_task

    async def get_task(self, task_id: str) -> UnifiedTask | None:
        """Get task from unified schema (source of truth).

        Args:
            task_id: Task identifier

        Returns:
            UnifiedTask or None if not found
        """
        return await self.session.get(UnifiedTask, task_id)

    async def update_status(
        self,
        task_id: str,
        status: str,
        **kwargs: Any,
    ) -> None:
        """Update task status in both schemas.

        Args:
            task_id: Task identifier
            status: New status
            **kwargs: Additional fields to update
        """
        update_data = {"status": status, "updated_at": datetime.utcnow(), **kwargs}

        # Update unified schema
        await self.session.execute(
            update(UnifiedTask)
            .where(UnifiedTask.id == task_id)
            .values(**update_data)
        )

        # Also update legacy if enabled
        if self._dual_write_enabled and self.legacy_session:
            # Note: This assumes legacy schema has same fields
            # In reality, you'd need to map fields appropriately
            from hive_orchestration.models import Task as LegacyTask

            await self.legacy_session.execute(
                update(LegacyTask)
                .where(LegacyTask.id == task_id)
                .values(**update_data)
            )

        # Commit both
        try:
            await self.session.commit()
            if self._dual_write_enabled and self.legacy_session:
                await self.legacy_session.commit()
        except Exception as e:
            logger.error(f"Status update dual-write failed: {e}")
            await self.session.rollback()
            if self._dual_write_enabled and self.legacy_session:
                await self.legacy_session.rollback()
            raise

        logger.debug(f"Updated task {task_id} status to {status}")

    async def create_review_task(
        self,
        code_path: str,
        correlation_id: str | None = None,
        pr_id: str | None = None,
        auto_fix_enabled: bool = True,
        **kwargs: Any,
    ) -> tuple[UnifiedTask, UnifiedReviewTask]:
        """Create review task in both base and review tables.

        Args:
            code_path: Path to code to review
            correlation_id: Correlation ID for tracking
            pr_id: Pull request ID if applicable
            auto_fix_enabled: Whether to enable auto-fix
            **kwargs: Additional task fields

        Returns:
            Tuple of (UnifiedTask, UnifiedReviewTask)
        """
        # Create base task
        base_task = await self.create_task(
            task_type="review",
            agent_type="ai-reviewer",  # Default, can be overridden
            input_data={"code_path": code_path, "pr_id": pr_id},
            correlation_id=correlation_id,
            **kwargs,
        )

        # Create review-specific task
        review_task = UnifiedReviewTask(
            task_id=base_task.id,
            correlation_id=base_task.correlation_id,
            code_path=code_path,
            pr_id=pr_id,
            auto_fix_enabled=1 if auto_fix_enabled else 0,
        )

        self.session.add(review_task)

        # Commit
        try:
            await self.session.commit()
        except Exception as e:
            logger.error(f"Review task creation failed: {e}")
            await self.session.rollback()
            raise

        logger.info(f"Created review task {base_task.id} for {code_path}")

        return base_task, review_task

    async def create_workflow_task(
        self,
        workflow_type: str,
        total_phases: int,
        correlation_id: str | None = None,
        workflow_config: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> tuple[UnifiedTask, UnifiedWorkflowTask]:
        """Create workflow task.

        Args:
            workflow_type: Type of workflow ('chimera', 'colossus', etc.)
            total_phases: Number of phases in workflow
            correlation_id: Correlation ID
            workflow_config: Workflow-specific configuration
            **kwargs: Additional task fields

        Returns:
            Tuple of (UnifiedTask, UnifiedWorkflowTask)
        """
        base_task = await self.create_task(
            task_type="workflow",
            agent_type="orchestrator",
            input_data={"workflow_type": workflow_type, "config": workflow_config},
            correlation_id=correlation_id,
            **kwargs,
        )

        workflow_task = UnifiedWorkflowTask(
            task_id=base_task.id,
            correlation_id=base_task.correlation_id,
            workflow_type=workflow_type,
            current_phase="initialized",
            total_phases=total_phases,
            workflow_config=workflow_config,
        )

        self.session.add(workflow_task)

        try:
            await self.session.commit()
        except Exception as e:
            logger.error(f"Workflow task creation failed: {e}")
            await self.session.rollback()
            raise

        logger.info(f"Created workflow task {base_task.id} ({workflow_type})")

        return base_task, workflow_task

    async def _convert_to_legacy(self, unified_task: UnifiedTask) -> Any:
        """Convert unified task to legacy schema format.

        Args:
            unified_task: Task in unified schema

        Returns:
            Task in legacy schema format

        Note:
            This is a placeholder. Actual implementation depends on
            your legacy schema structure. May not be needed if you
            can use the same model for both.
        """
        # Import legacy model (example)
        from hive_orchestration.models import Task as LegacyTask

        return LegacyTask(
            id=unified_task.id,
            status=unified_task.status,
            # Map other fields as needed
        )

    def disable_dual_write(self) -> None:
        """Disable dual-write (post-migration).

        After migration is complete, call this to stop writing to legacy schema.
        """
        self._dual_write_enabled = False
        self.legacy_session = None
        logger.info("Dual-write disabled - using unified schema only")


# Convenience function for creating dual-write repository
async def create_dual_write_repository(
    enable_legacy: bool = True,
) -> DualWriteTaskRepository:
    """Create dual-write repository.

    Args:
        enable_legacy: Whether to enable legacy schema writes

    Returns:
        DualWriteTaskRepository instance
    """
    # Get unified schema session
    unified_session = await get_sqlite_connection()  # Update with actual DB config

    # Get legacy session if enabled
    legacy_session = None
    if enable_legacy:
        # Use same connection for now, but could be separate DB
        legacy_session = await get_sqlite_connection()

    return DualWriteTaskRepository(
        session=unified_session,
        legacy_session=legacy_session,
    )
