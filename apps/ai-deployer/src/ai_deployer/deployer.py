"""
Deployment orchestrator that manages deployment strategies and execution
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

from hive_logging import get_logger

logger = get_logger(__name__)


class DeploymentStrategy(Enum):
    """Available deployment strategies"""

    DIRECT = ("direct",)
    BLUE_GREEN = ("blue-green",)
    ROLLING = ("rolling",)
    CANARY = "canary"


@dataclass
class DeploymentResult:
    """Result of a deployment operation"""

    success: bool
    strategy: DeploymentStrategy
    deployment_id: str | None = None
    error: str | None = None
    rollback_attempted: bool = False
    metrics: dict[str, Any] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert result to dictionary"""
        return {
            "success": self.success,
            "strategy": self.strategy.value,
            "deployment_id": self.deployment_id,
            "error": self.error,
            "rollback_attempted": self.rollback_attempted,
            "metrics": self.metrics or {},
        }


@dataclass
class HealthStatus:
    """Health check result"""

    healthy: bool
    message: str | None = None
    checks: dict[str, bool] = None


class DeploymentOrchestrator:
    """
    Orchestrates deployment operations using various strategies
    """

    def __init__(self, config: Optional[dict[str, Any]] = None) -> None:
        """
        Initialize deployment orchestrator

        Args:
            config: Optional configuration dictionary
        """
        self.config = config or {}
        self.strategies = self._initialize_strategies()
        self.default_strategy = DeploymentStrategy.DIRECT

    def _initialize_strategies(self) -> dict[DeploymentStrategy, Any]:
        """Initialize deployment strategies"""
        from .strategies.docker import DockerDeploymentStrategy
        from .strategies.kubernetes import KubernetesDeploymentStrategy
        from .strategies.ssh import SSHDeploymentStrategy

        return {
            DeploymentStrategy.DIRECT: SSHDeploymentStrategy(self.config),
            DeploymentStrategy.BLUE_GREEN: SSHDeploymentStrategy(self.config),
            DeploymentStrategy.ROLLING: DockerDeploymentStrategy(self.config),
            DeploymentStrategy.CANARY: KubernetesDeploymentStrategy(self.config),
        }

    async def deploy_async(self, task: dict[str, Any]) -> DeploymentResult:
        """
        Deploy application based on task configuration

        Args:
            task: Deployment task containing configuration

        Returns:
            DeploymentResult with status and metrics
        """
        task_id = task.get("id", "unknown")
        deployment_id = f"deploy-{task_id}-{int(asyncio.get_event_loop().time())}"

        try:
            logger.info(f"Starting deployment {deployment_id} for task {task_id}")

            # Select deployment strategy
            strategy = self._select_strategy(task)
            logger.info(f"Using deployment strategy: {strategy.value}")

            # Get strategy implementation
            strategy_impl = self.strategies.get(strategy)
            if not strategy_impl:
                raise ValueError(f"Strategy {strategy} not implemented")

            # Execute deployment
            result = await self._execute_deployment_async(strategy_impl, task, deployment_id)

            # Post-deployment validation
            if result.success:
                await self._validate_deployment_async(task, deployment_id)

            return result

        except Exception as e:
            logger.error(f"Deployment {deployment_id} failed: {e}", exc_info=True)

            # Attempt rollback
            rollback_success = await self._attempt_rollback_async(task, deployment_id)

            return DeploymentResult(
                success=False,
                strategy=strategy,
                deployment_id=deployment_id,
                error=str(e),
                rollback_attempted=True,
                metrics={"rollback_success": rollback_success},
            )

    def _select_strategy(self, task: dict[str, Any]) -> DeploymentStrategy:
        """
        Select deployment strategy based on task configuration

        Args:
            task: Deployment task

        Returns:
            Selected deployment strategy
        """
        # Check task configuration for strategy preference
        strategy_name = task.get("deployment_strategy", "").lower()

        # Map to enum
        strategy_map = {
            "direct": DeploymentStrategy.DIRECT,
            "blue-green": DeploymentStrategy.BLUE_GREEN,
            "rolling": DeploymentStrategy.ROLLING,
            "canary": DeploymentStrategy.CANARY,
        }

        strategy = strategy_map.get(strategy_name, self.default_strategy)

        # Validate strategy is appropriate for environment
        if not self._validate_strategy_compatibility(strategy, task):
            logger.warning(f"Strategy {strategy.value} not compatible, falling back to direct")
            strategy = DeploymentStrategy.DIRECT

        return strategy

    def _validate_strategy_compatibility(self, strategy: DeploymentStrategy, task: dict[str, Any]) -> bool:
        """
        Validate if strategy is compatible with deployment environment

        Args:
            strategy: Selected deployment strategy
            task: Deployment task

        Returns:
            True if strategy is compatible
        """
        environment = task.get("environment", {})

        # Blue-green requires load balancer
        if strategy == DeploymentStrategy.BLUE_GREEN:
            return environment.get("has_load_balancer", False)

        # Canary requires Kubernetes
        if strategy == DeploymentStrategy.CANARY:
            return environment.get("platform") == "kubernetes"

        # Rolling requires container orchestration
        if strategy == DeploymentStrategy.ROLLING:
            return environment.get("platform") in ["docker", "kubernetes"]

        # Direct deployment is always available
        return True

    async def _execute_deployment_async(
        self, strategy_impl: Any, task: dict[str, Any], deployment_id: str,
    ) -> DeploymentResult:
        """
        Execute deployment using selected strategy

        Args:
            strategy_impl: Strategy implementation
            task: Deployment task
            deployment_id: Unique deployment ID

        Returns:
            Deployment result
        """
        # Pre-deployment checks
        pre_checks = await strategy_impl.pre_deployment_checks(task)
        if not pre_checks["success"]:
            raise RuntimeError(f"Pre-deployment checks failed: {pre_checks['errors']}")

        # Execute deployment
        deploy_result = await strategy_impl.deploy_async(task, deployment_id)

        # Post-deployment actions
        if deploy_result["success"]:
            await strategy_impl.post_deployment_actions(task, deployment_id)

        return DeploymentResult(
            success=deploy_result["success"],
            strategy=strategy_impl.strategy,
            deployment_id=deployment_id,
            metrics=deploy_result.get("metrics", {}),
        )

    async def _validate_deployment_async(self, task: dict[str, Any], deployment_id: str) -> bool:
        """
        Validate deployment was successful

        Args:
            task: Deployment task
            deployment_id: Deployment ID

        Returns:
            True if deployment is valid
        """
        try:
            # Run health checks
            health_status = await self.check_health_async(task)

            if not health_status.healthy:
                logger.error(f"Deployment {deployment_id} validation failed: {health_status.message}")
                return False

            # Run smoke tests if configured
            if task.get("run_smoke_tests", False):
                smoke_result = await self._run_smoke_tests_async(task)
                if not smoke_result:
                    logger.error(f"Deployment {deployment_id} smoke tests failed")
                    return False

            logger.info(f"Deployment {deployment_id} validated successfully")
            return True

        except Exception as e:
            logger.error(f"Deployment validation error: {e}", exc_info=True)
            return False

    async def _attempt_rollback_async(self, task: dict[str, Any], deployment_id: str) -> bool:
        """
        Attempt to rollback failed deployment

        Args:
            task: Deployment task
            deployment_id: Failed deployment ID

        Returns:
            True if rollback successful
        """
        try:
            logger.info(f"Attempting rollback for deployment {deployment_id}")

            # Get previous deployment info
            previous = task.get("previous_deployment", {})
            if not previous:
                logger.warning("No previous deployment info for rollback")
                return False

            # Use direct strategy for rollback (safest)
            strategy_impl = self.strategies[DeploymentStrategy.DIRECT]

            # Execute rollback
            rollback_result = await strategy_impl.rollback(task, deployment_id, previous)

            if rollback_result["success"]:
                logger.info(f"Rollback successful for deployment {deployment_id}")
                return True
            else:
                logger.error(f"Rollback failed for deployment {deployment_id}: {rollback_result.get('error')}")
                return False

        except Exception as e:
            logger.error(f"Rollback error: {e}", exc_info=True)
            return False

    async def check_health_async(self, task: dict[str, Any]) -> HealthStatus:
        """
        Check health of deployed application

        Args:
            task: Deployment task with endpoint info

        Returns:
            Health status
        """
        try:
            health_checks = {}

            # Check application endpoint
            endpoint = task.get("health_endpoint", "/health")
            app_health = await self._check_endpoint_async(task, endpoint)
            health_checks["application"] = app_health

            # Check dependencies if configured
            dependencies = task.get("health_dependencies", [])
            for dep in dependencies:
                dep_health = await self._check_dependency_async(dep)
                health_checks[dep["name"]] = dep_health

            # Overall health is True if all checks pass
            overall_healthy = all(health_checks.values())

            return HealthStatus(
                healthy=overall_healthy,
                message=("All health checks passed" if overall_healthy else "Some health checks failed"),
                checks=health_checks,
            )

        except Exception as e:
            logger.error(f"Health check error: {e}", exc_info=True)
            return HealthStatus(healthy=False, message=f"Health check error: {e}")

    async def _check_endpoint_async(self, task: dict[str, Any], endpoint: str) -> bool:
        """Check if application endpoint is healthy"""
        # Implementation would make HTTP request to endpoint
        # For now, simulate check
        await asyncio.sleep(0.5)
        return True  # Placeholder

    async def _check_dependency_async(self, dependency: dict[str, Any]) -> bool:
        """Check if dependency is healthy"""
        # Implementation would check dependency health
        # For now, simulate check
        await asyncio.sleep(0.2)
        return True  # Placeholder

    async def _run_smoke_tests_async(self, task: dict[str, Any]) -> bool:
        """Run smoke tests on deployed application"""
        # Implementation would run configured smoke tests
        # For now, simulate test run
        await asyncio.sleep(1.0)
        return True  # Placeholder
