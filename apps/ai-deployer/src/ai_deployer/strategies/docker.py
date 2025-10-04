"""Docker-based deployment strategy
"""

import asyncio
from typing import Any

from hive_logging import get_logger
from hive_performance import track_request

from ..deployer import DeploymentStrategy
from .base import BaseDeploymentStrategy

logger = get_logger(__name__)


class DockerDeploymentStrategy(BaseDeploymentStrategy):
    """Docker-based deployment strategy for containerized applications
    """

    def __init__(self, config: dict[str, Any]) -> None:
        """Initialize Docker deployment strategy"""
        super().__init__(config)
        self.strategy = DeploymentStrategy.ROLLING

    async def pre_deployment_checks_async(self, task: dict[str, Any]) -> dict[str, Any]:
        """Run pre-deployment checks for Docker deployment

        Args:
            task: Deployment task

        Returns:
            Dictionary with check results

        """
        errors = []

        try:
            # Validate task configuration
            if not await self.validate_configuration(task):
                errors.append("Invalid task configuration")

            # Check Docker daemon accessibility
            docker_available = await self._check_docker_daemon_async()
            if not docker_available:
                errors.append("Docker daemon not accessible")

            # Validate Docker image exists or can be built
            image_config = task.get("docker_image", {})
            if not image_config:
                errors.append("Docker image configuration missing")
            else:
                image_valid = await self._validate_docker_image_async(image_config)
                if not image_valid:
                    errors.append("Docker image validation failed")

            # Check Docker registry credentials if needed
            registry_config = task.get("docker_registry", {})
            if registry_config:
                registry_valid = await self._check_registry_access_async(registry_config)
                if not registry_valid:
                    errors.append("Docker registry access failed")

            return {"success": len(errors) == 0, "errors": errors}

        except Exception as e:
            logger.error(f"Docker pre-deployment check error: {e}")
            return {"success": False, "errors": [f"Pre-deployment check failed: {e}"]}

    @track_request("docker_deployment", labels={"strategy": "docker"})
    async def deploy_async(self, task: dict[str, Any], deployment_id: str) -> dict[str, Any]:
        """Execute Docker deployment

        Args:
            task: Deployment task
            deployment_id: Unique deployment identifier

        Returns:
            Deployment result dictionary

        """
        try:
            logger.info(f"Starting Docker deployment {deployment_id}")

            # Build or pull Docker image
            image_result = await self._prepare_docker_image_async(task, deployment_id)
            if not image_result["success"]:
                return {"success": False, "error": f"Image preparation failed: {image_result['error']}"}

            image_name = image_result["image_name"]

            # Stop existing containers if doing rolling deployment
            if self.strategy == DeploymentStrategy.ROLLING:
                stop_result = await self._stop_existing_containers_async(task)
                if not stop_result:
                    logger.warning("Failed to stop some existing containers")

            # Run new container
            container_result = await self._run_container_async(task, image_name, deployment_id)
            if not container_result["success"]:
                return {"success": False, "error": f"Container startup failed: {container_result['error']}"}

            container_id = container_result["container_id"]

            # Wait for container to be healthy
            health_check = await self._wait_for_container_health_async(container_id)
            if not health_check:
                # Container failed health check - stop it
                await self._stop_container_async(container_id)
                return {"success": False, "error": "Container failed health check"}

            # Update load balancer or proxy configuration
            lb_result = await self._update_load_balancer_async(task, container_id)

            logger.info(f"Docker deployment {deployment_id} completed successfully")

            return {
                "success": True,
                "metrics": {
                    "image_size": image_result.get("image_size", 0),
                    "container_startup_time": container_result.get("startup_time", 0),
                },
                "deployment_info": {
                    "image_name": image_name,
                    "container_id": container_id,
                    "load_balancer_updated": lb_result,
                },
            }

        except Exception as e:
            logger.error(f"Docker deployment {deployment_id} error: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    async def rollback_async(
        self,
        task: dict[str, Any],
        deployment_id: str,
        previous_deployment: dict[str, Any],
    ) -> dict[str, Any]:
        """Rollback Docker deployment to previous version

        Args:
            task: Deployment task
            deployment_id: Failed deployment ID
            previous_deployment: Previous deployment info

        Returns:
            Rollback result dictionary

        """
        try:
            logger.info(f"Starting Docker rollback for deployment {deployment_id}")

            # Get previous container/image info
            previous_info = previous_deployment.get("deployment_info", {})
            previous_image = (previous_info.get("image_name"),)
            current_container = previous_info.get("container_id")

            if not previous_image:
                return {"success": False, "error": "No previous image information for rollback"}

            # Stop current failed container
            if current_container:
                await self._stop_container_async(current_container)

            # Start container with previous image
            rollback_result = await self._run_container_async(task, previous_image, f"rollback-{deployment_id}")

            if not rollback_result["success"]:
                return {"success": False, "error": f"Rollback container startup failed: {rollback_result['error']}"}

            rollback_container = rollback_result["container_id"]

            # Wait for rollback container to be healthy
            health_check = await self._wait_for_container_health_async(rollback_container)

            if not health_check:
                await self._stop_container_async(rollback_container)
                return {"success": False, "error": "Rollback container failed health check"}

            # Update load balancer back to rollback container
            await self._update_load_balancer_async(task, rollback_container)

            logger.info(f"Docker rollback for deployment {deployment_id} completed")

            return {
                "success": True,
                "rollback_info": {"rolled_back_to_image": previous_image, "rollback_container_id": rollback_container},
            }

        except Exception as e:
            logger.error(f"Docker rollback error for {deployment_id}: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    async def post_deployment_actions_async(self, task: dict[str, Any], deployment_id: str) -> None:
        """Run post-deployment actions for Docker deployment

        Args:
            task: Deployment task
            deployment_id: Deployment identifier

        """
        try:
            # Cleanup old Docker images (keep last 3 versions)
            await self._cleanup_old_images_async(task)

            # Remove stopped containers
            await self._cleanup_stopped_containers_async(task)

            # Update monitoring and logging configuration
            await self._update_container_monitoring_async(task, deployment_id)

        except Exception as e:
            logger.error(f"Docker post-deployment actions error: {e}")

    def get_required_task_fields(self) -> list[str]:
        """Get required fields for Docker deployment"""
        return ["docker_image", "container_config"]

    # Helper methods

    async def _check_docker_daemon_async(self) -> bool:
        """Check if Docker daemon is accessible"""
        try:
            # Simulate Docker daemon check
            await asyncio.sleep(0.2)
            return True  # Placeholder
        except Exception as e:
            logger.error(f"Docker daemon check failed: {e}")
            return False

    async def _validate_docker_image_async(self, image_config: dict[str, Any]) -> bool:
        """Validate Docker image configuration"""
        try:
            # Check if image exists locally or can be pulled
            await asyncio.sleep(0.3)
            return True  # Placeholder
        except Exception as e:
            logger.error(f"Docker image validation failed: {e}")
            return False

    async def _check_registry_access_async(self, registry_config: dict[str, Any]) -> bool:
        """Check Docker registry access"""
        try:
            # Test registry login
            await asyncio.sleep(0.2)
            return True  # Placeholder
        except Exception as e:
            logger.error(f"Registry access check failed: {e}")
            return False

    async def _prepare_docker_image_async(self, task: dict[str, Any], deployment_id: str) -> dict[str, Any]:
        """Build or pull Docker image"""
        try:
            image_config = task["docker_image"]

            # Simulate image preparation
            await asyncio.sleep(2.0)

            image_name = f"{image_config.get('name', 'app')}:{deployment_id}"

            return {
                "success": True,
                "image_name": image_name,
                "image_size": 150 * 1024 * 1024,  # 150 MB placeholder
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _stop_existing_containers_async(self, task: dict[str, Any]) -> bool:
        """Stop existing containers for rolling deployment"""
        try:
            # Find and stop existing containers
            await asyncio.sleep(0.5)
            return True  # Placeholder
        except Exception as e:
            logger.error(f"Failed to stop existing containers: {e}")
            return False

    async def _run_container_async(self, task: dict[str, Any], image_name: str, deployment_id: str) -> dict[str, Any]:
        """Run Docker container"""
        try:
            # Simulate container startup
            await asyncio.sleep(1.0)

            container_id = f"container_{deployment_id}"

            return {"success": True, "container_id": container_id, "startup_time": 1.0}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _wait_for_container_health_async(self, container_id: str) -> bool:
        """Wait for container to become healthy"""
        try:
            # Simulate health check waiting
            await asyncio.sleep(2.0)
            return True  # Placeholder
        except Exception as e:
            logger.error(f"Container health check failed: {e}")
            return False

    async def _stop_container_async(self, container_id: str) -> bool:
        """Stop a Docker container"""
        try:
            # Simulate container stop
            await asyncio.sleep(0.3)
            return True
        except Exception as e:
            logger.error(f"Failed to stop container {container_id}: {e}")
            return False

    async def _update_load_balancer_async(self, task: dict[str, Any], container_id: str) -> bool:
        """Update load balancer configuration"""
        try:
            # Simulate load balancer update
            await asyncio.sleep(0.5)
            return True  # Placeholder
        except Exception as e:
            logger.error(f"Load balancer update failed: {e}")
            return False

    async def _cleanup_old_images_async(self, task: dict[str, Any]) -> None:
        """Cleanup old Docker images"""
        try:
            # Remove old image versions
            await asyncio.sleep(0.3)
        except Exception as e:
            logger.error(f"Image cleanup failed: {e}")

    async def _cleanup_stopped_containers_async(self, task: dict[str, Any]) -> None:
        """Remove stopped containers"""
        try:
            # Remove stopped containers
            await asyncio.sleep(0.2)
        except Exception as e:
            logger.error(f"Container cleanup failed: {e}")

    async def _update_container_monitoring_async(self, task: dict[str, Any], deployment_id: str) -> None:
        """Update container monitoring configuration"""
        try:
            # Update monitoring configs
            await asyncio.sleep(0.1)
        except Exception as e:
            logger.error(f"Monitoring update failed: {e}")
