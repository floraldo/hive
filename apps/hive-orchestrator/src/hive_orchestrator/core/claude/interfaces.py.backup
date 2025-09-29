"""
Claude Service Interfaces
Defines the abstract interfaces and contracts for Claude services.
No business logic, only interface definitions.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class ClaudeServiceInterface(ABC):
    """Abstract interface for Claude API service"""

    @abstractmethod
    async def call_claude_async(
        self, prompt: str, max_tokens: int = 1000, temperature: float = 0.7, **kwargs
    ) -> Dict[str, Any]:
        """
        Make an async call to Claude API.

        Args:
            prompt: The prompt to send to Claude
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature
            **kwargs: Additional parameters

        Returns:
            Response from Claude API
        """
        pass

    @abstractmethod
    def get_metrics(self) -> Dict[str, Any]:
        """Get service metrics"""
        pass

    @abstractmethod
    def clear_cache(self) -> None:
        """Clear response cache"""
        pass


class PlannerBridgeInterface(ABC):
    """Abstract interface for Claude Planner Bridge"""

    @abstractmethod
    async def create_plan_async(
        self, task_description: str, context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create a plan for the given task.

        Args:
            task_description: Description of the task
            context: Optional context information

        Returns:
            Plan details
        """
        pass

    @abstractmethod
    async def refine_plan_async(self, plan: Dict[str, Any], feedback: str) -> Dict[str, Any]:
        """
        Refine an existing plan based on feedback.

        Args:
            plan: Existing plan to refine
            feedback: Feedback for refinement

        Returns:
            Refined plan
        """
        pass


class ReviewerBridgeInterface(ABC):
    """Abstract interface for Claude Reviewer Bridge"""

    @abstractmethod
    async def review_code_async(
        self, code: str, language: str = "python", context: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Review code using Claude.

        Args:
            code: Code to review
            language: Programming language
            context: Optional context

        Returns:
            Review results
        """
        pass

    @abstractmethod
    async def suggest_improvements_async(self, code: str, issues: List[str]) -> Dict[str, Any]:
        """
        Suggest improvements for identified issues.

        Args:
            code: Code with issues
            issues: List of identified issues

        Returns:
            Improvement suggestions
        """
        pass


class MonitoringInterface(ABC):
    """Abstract interface for monitoring services"""

    @abstractmethod
    def record_metric(self, metric_name: str, value: float, tags: Optional[Dict[str, str]] = None) -> None:
        """Record a metric"""
        pass

    @abstractmethod
    def start_span(self, operation_name: str) -> Any:
        """Start a monitoring span"""
        pass

    @abstractmethod
    def get_health_status(self) -> Dict[str, Any]:
        """Get health status"""
        pass
