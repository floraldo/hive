"""
Base deployment strategy interface
"""

from abc import ABC, abstractmethod
from typing import Any

from hive_logging import get_logger

from ..deployer import DeploymentStrategy

logger = get_logger(__name__)


class BaseDeploymentStrategy(ABC):
    """
    Abstract base class for deployment strategies
    """

    def __init__(self, config: dict[str, Any]) -> None:
        """
        Initialize strategy with configuration

        Args:
            config: Strategy configuration
        """
        self.config = config
        self.strategy = DeploymentStrategy.DIRECT

    @abstractmethod
    async def pre_deployment_checks_async(self, task: dict[str, Any]) -> dict[str, Any]:
        """
        Run pre-deployment validation checks

        Args:
            task: Deployment task

        Returns:
            Dictionary with success status and any errors
        """
        pass

    @abstractmethod
    async def deploy_async(self, task: dict[str, Any], deployment_id: str) -> dict[str, Any]:
        """
        Execute the deployment

        Args:
            task: Deployment task
            deployment_id: Unique deployment identifier

        Returns:
            Dictionary with deployment result
        """
        pass

    @abstractmethod
    async def rollback_async(
        self, task: dict[str, Any], deployment_id: str, previous_deployment: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Rollback deployment to previous version

        Args:
            task: Deployment task
            deployment_id: Failed deployment identifier
            previous_deployment: Previous deployment information

        Returns:
            Dictionary with rollback result
        """
        pass

    @abstractmethod
    async def post_deployment_actions_async(self, task: dict[str, Any], deployment_id: str) -> None:
        """
        Run post-deployment actions (cleanup, notifications, etc.)

        Args:
            task: Deployment task
            deployment_id: Deployment identifier
        """
        pass

    async def validate_configuration_async(self, task: dict[str, Any]) -> bool:
        """
        Validate that task configuration is compatible with this strategy

        Args:
            task: Deployment task

        Returns:
            True if configuration is valid
        """
        required_fields = self.get_required_task_fields()

        for field in required_fields:
            if field not in task:
                logger.error(f"Missing required field {field} for {self.strategy.value} deployment")
                return False

        return True

    @abstractmethod
    def get_required_task_fields(self) -> list[str]:
        """
        Get list of required fields in task configuration

        Returns:
            List of required field names
        """
        pass
