"""
Base deployment strategy interface
"""

from abc import ABC, abstractmethod
from typing import Any, Dict

from hive_logging import get_logger

from ..deployer import DeploymentStrategy

logger = get_logger(__name__)


class BaseDeploymentStrategy(ABC):
    """
    Abstract base class for deployment strategies
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize strategy with configuration

        Args:
            config: Strategy configuration
        """
        self.config = config
        self.strategy = DeploymentStrategy.DIRECT

    @abstractmethod
    async def pre_deployment_checks(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run pre-deployment validation checks

        Args:
            task: Deployment task

        Returns:
            Dictionary with success status and any errors
        """
        pass

    @abstractmethod
    async def deploy(self, task: Dict[str, Any], deployment_id: str) -> Dict[str, Any]:
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
    async def rollback(
        self,
        task: Dict[str, Any],
        deployment_id: str,
        previous_deployment: Dict[str, Any],
    ) -> Dict[str, Any]:
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
    async def post_deployment_actions(
        self, task: Dict[str, Any], deployment_id: str
    ) -> None:
        """
        Run post-deployment actions (cleanup, notifications, etc.)

        Args:
            task: Deployment task
            deployment_id: Deployment identifier
        """
        pass

    async def validate_configuration(self, task: Dict[str, Any]) -> bool:
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
                logger.error(
                    f"Missing required field {field} for {self.strategy.value} deployment"
                )
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
