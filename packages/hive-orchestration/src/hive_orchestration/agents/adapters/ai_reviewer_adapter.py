"""Adapter for ai-reviewer agent.

Wraps the existing ai-reviewer implementation to conform to StandardAgent interface.
During migration, this adapter:
- Translates unified task format to ai-reviewer format
- Emits unified events for observability
- Provides health checks
- Maintains backwards compatibility
"""

from typing import Any

from hive_bus import UnifiedEventType
from hive_logging import get_logger

from ..base_agent import AgentCapability, StandardAgent

logger = get_logger(__name__)


class AIReviewerAdapter(StandardAgent):
    """Adapter for ai-reviewer agent.

    This adapter wraps an existing ai-reviewer instance and provides:
    - StandardAgent interface implementation
    - Event emission for review lifecycle
    - Health monitoring
    - Task format translation
    """

    def __init__(
        self,
        wrapped_agent: Any | None = None,
        agent_id: str = "ai-reviewer-adapter",
        event_bus: Any | None = None,
    ):
        """Initialize ai-reviewer adapter.

        Args:
            wrapped_agent: Optional existing ai-reviewer instance to wrap
            agent_id: Unique identifier for this adapter
            event_bus: Optional event bus for emitting events
        """
        super().__init__(
            agent_id=agent_id,
            agent_type="ai-reviewer",
            capabilities=[AgentCapability.REVIEW],
            event_bus=event_bus,
        )
        self._wrapped_agent = wrapped_agent

    async def execute(self, task_data: dict[str, Any]) -> dict[str, Any]:
        """Execute code review task.

        Args:
            task_data: Task data with structure:
                - code_path: Path to code to review
                - pr_id: Optional PR identifier
                - auto_fix: Whether to attempt auto-fixes

        Returns:
            Review result with:
                - review_score: Quality score (0-100)
                - violations: List of issues found
                - suggestions: Improvement suggestions
                - auto_fix_result: Auto-fix results if enabled
        """
        correlation_id = task_data.get("correlation_id", "unknown")

        # Emit review requested event
        self.emit_event(
            event_type=UnifiedEventType.REVIEW_REQUESTED,
            correlation_id=correlation_id,
            payload={"code_path": task_data.get("code_path")},
        )

        try:
            # If wrapped agent exists, delegate to it
            if self._wrapped_agent:
                result = await self._call_wrapped_agent(task_data)
            else:
                # Placeholder implementation for migration prep
                result = self._placeholder_review(task_data)

            # Emit review completed event
            self.emit_event(
                event_type=UnifiedEventType.REVIEW_COMPLETED,
                correlation_id=correlation_id,
                payload={"review_score": result.get("review_score", 0)},
            )

            return result

        except Exception as e:
            logger.error(f"Review execution failed: {e}")
            # Emit error event
            self.emit_event(
                event_type=UnifiedEventType.AGENT_ERROR,
                correlation_id=correlation_id,
                payload={"error": str(e)},
            )
            raise

    async def _call_wrapped_agent(self, task_data: dict[str, Any]) -> dict[str, Any]:
        """Call the wrapped ai-reviewer agent.

        This method translates between unified format and agent-specific format.
        """
        # TODO: Implement actual translation when integrating with real ai-reviewer
        logger.info("Calling wrapped ai-reviewer agent")
        # Placeholder - actual implementation will call wrapped_agent methods
        return {"review_score": 85, "violations": [], "suggestions": []}

    def _placeholder_review(self, task_data: dict[str, Any]) -> dict[str, Any]:
        """Placeholder review implementation for migration prep.

        This allows the adapter to be tested before full ai-reviewer integration.
        """
        logger.info(f"Placeholder review for: {task_data.get('code_path')}")
        return {
            "review_score": 90,
            "violations": [],
            "suggestions": ["Example suggestion"],
            "auto_fix_result": None,
        }

    async def health_check(self) -> dict[str, Any]:
        """Check ai-reviewer adapter health.

        Returns:
            Health status dictionary
        """
        if self._wrapped_agent:
            # If wrapped agent has health check, use it
            if hasattr(self._wrapped_agent, "health_check"):
                try:
                    return await self._wrapped_agent.health_check()
                except Exception as e:
                    logger.error(f"Wrapped agent health check failed: {e}")
                    return {"status": "unhealthy", "message": str(e)}

        # Default health check
        return {
            "status": "healthy",
            "message": "AI Reviewer adapter operational",
            "wrapped_agent": self._wrapped_agent is not None,
        }
