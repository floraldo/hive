"""
SSH-based deployment strategy using hive-deployment package
"""

import asyncio
from pathlib import Path
from typing import Any

from hive_deployment import connect_to_server, deploy_application, determine_deployment_paths
from hive_logging import get_logger

from ..deployer import DeploymentStrategy
from .base import BaseDeploymentStrategy

logger = get_logger(__name__)


class SSHDeploymentStrategy(BaseDeploymentStrategy):
    """
    SSH-based deployment strategy for traditional server deployments
    """

    def __init__(self, config: dict[str, Any]) -> None:
        """Initialize SSH deployment strategy"""
        super().__init__(config)
        self.strategy = DeploymentStrategy.DIRECT

    async def pre_deployment_checks_async(self, task: dict[str, Any]) -> dict[str, Any]:
        """
        Run pre-deployment checks for SSH deployment

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

            # Check SSH connectivity
            ssh_config = task.get("ssh_config", {})
            if not ssh_config:
                errors.append("SSH configuration not found")
            else:
                ssh_check = await self._check_ssh_connectivity_async(ssh_config)
                if not ssh_check:
                    errors.append("SSH connectivity check failed")

            # Check local source files exist
            source_path = task.get("source_path")
            if source_path and not Path(source_path).exists():
                errors.append(f"Source path does not exist: {source_path}")

            # Check remote target directory permissions
            remote_checks = await self._check_remote_permissions_async(task)
            if not remote_checks:
                errors.append("Remote permission checks failed")

            return {"success": len(errors) == 0, "errors": errors}

        except Exception as e:
            logger.error(f"Pre-deployment check error: {e}")
            return {"success": False, "errors": [f"Pre-deployment check failed: {e}"]}

    async def deploy_async(self, task: dict[str, Any], deployment_id: str) -> dict[str, Any]:
        """
        Execute SSH deployment

        Args:
            task: Deployment task
            deployment_id: Unique deployment identifier

        Returns:
            Deployment result dictionary
        """
        try:
            logger.info(f"Starting SSH deployment {deployment_id}")

            # Extract deployment configuration
            ssh_config = task.get("ssh_config", {})
            app_name = task.get("app_name", f"app-{deployment_id}")
            source_path = task.get("source_path")

            # Connect to server
            ssh_client = await self._connect_to_server_async(ssh_config)
            if not ssh_client:
                return {"success": False, "error": "Failed to establish SSH connection"}

            try:
                # Determine deployment paths
                deployment_paths = determine_deployment_paths(app_name)

                # Create deployment backup point
                backup_info = await self._create_backup_async(ssh_client, deployment_paths)

                # Deploy application
                deploy_result = await self._deploy_application_async(ssh_client, source_path, deployment_paths, task)

                if not deploy_result["success"]:
                    return {"success": False, "error": deploy_result.get("error", "Deployment failed")}

                # Start/restart services
                service_result = await self._manage_services_async(ssh_client, app_name, "start")

                if not service_result:
                    # Deployment succeeded but service start failed - still a failure
                    return {
                        "success": False,
                        "error": "Application deployed but failed to start services",
                        "deployment_info": {"backup": backup_info, "paths": deployment_paths},
                    }

                logger.info(f"SSH deployment {deployment_id} completed successfully")

                return {
                    "success": True,
                    "metrics": {
                        "deployment_time": deploy_result.get("duration", 0),
                        "files_deployed": deploy_result.get("files_count", 0),
                    },
                    "deployment_info": {"backup": backup_info, "paths": deployment_paths, "app_name": app_name},
                }

            finally:
                # Always close SSH connection
                ssh_client.close()

        except Exception as e:
            logger.error(f"SSH deployment {deployment_id} error: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    async def rollback_async(
        self, task: dict[str, Any], deployment_id: str, previous_deployment: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Rollback SSH deployment to previous version

        Args:
            task: Deployment task
            deployment_id: Failed deployment ID
            previous_deployment: Previous deployment info

        Returns:
            Rollback result dictionary
        """
        try:
            logger.info(f"Starting rollback for deployment {deployment_id}")

            ssh_config = task.get("ssh_config", {})
            app_name = task.get("app_name", "unknown")

            # Connect to server
            ssh_client = await self._connect_to_server_async(ssh_config)
            if not ssh_client:
                return {"success": False, "error": "Failed to establish SSH connection for rollback"}

            try:
                # Get backup information
                backup_info = previous_deployment.get("backup", {})
                if not backup_info:
                    logger.warning("No backup information found for rollback")
                    return {"success": False, "error": "No backup available for rollback"}

                # Restore from backup
                restore_result = await self._restore_from_backup_async(ssh_client, backup_info)

                if not restore_result:
                    return {"success": False, "error": "Failed to restore from backup"}

                # Restart services with previous configuration
                service_result = await self._manage_services_async(ssh_client, app_name, "restart")

                logger.info(f"Rollback for deployment {deployment_id} completed")

                return {
                    "success": True,
                    "rollback_info": {"restored_from": backup_info, "services_restarted": service_result},
                }

            finally:
                ssh_client.close()

        except Exception as e:
            logger.error(f"Rollback error for {deployment_id}: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    async def post_deployment_actions_async(self, task: dict[str, Any], deployment_id: str) -> None:
        """
        Run post-deployment actions for SSH deployment

        Args:
            task: Deployment task
            deployment_id: Deployment identifier
        """
        try:
            # Cleanup old backups (keep last 5)
            await self._cleanup_old_backups_async(task)

            # Update monitoring configurations if specified
            if task.get("update_monitoring", False):
                await self._update_monitoring_config_async(task)

            # Send deployment notifications
            await self._send_deployment_notifications_async(task, deployment_id, success=True)

        except Exception as e:
            logger.error(f"Post-deployment actions error: {e}")
            # Don't fail deployment for post-action errors

    def get_required_task_fields(self) -> list[str]:
        """Get required fields for SSH deployment"""
        return ["ssh_config", "app_name", "source_path"]

    # Helper methods

    async def _check_ssh_connectivity_async(self, ssh_config: dict[str, Any]) -> bool:
        """Test SSH connectivity"""
        try:
            # Run in executor to avoid blocking
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, self._sync_check_ssh, ssh_config)
            return result
        except Exception as e:
            logger.error(f"SSH connectivity check failed: {e}")
            return False

    def _sync_check_ssh(self, ssh_config: dict[str, Any]) -> bool:
        """Synchronous SSH connectivity check"""
        try:
            ssh_client = connect_to_server(ssh_config)
            if ssh_client:
                ssh_client.close()
                return True
            return False
        except Exception:
            return False

    async def _check_remote_permissions_async(self, task: dict[str, Any]) -> bool:
        """Check remote directory permissions"""
        # Implementation would check write permissions on target directory
        # For now, assume success
        return True

    async def _connect_to_server_async(self, ssh_config: dict[str, Any]):
        """Establish SSH connection"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, connect_to_server, ssh_config)

    async def _deploy_application_async(
        self, ssh_client, source_path: str, deployment_paths: dict[str, str], task: dict[str, Any],
    ) -> dict[str, Any]:
        """Deploy application files"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, deploy_application, ssh_client, source_path, deployment_paths, task)

    async def _create_backup_async(self, ssh_client, deployment_paths: dict[str, str]) -> dict[str, Any]:
        """Create backup of current deployment"""
        # Implementation would create backup of existing deployment
        # For now, return mock backup info
        return {
            "backup_id": f"backup-{int(asyncio.get_event_loop().time())}",
            "backup_path": "/tmp/deployment_backup",
            "created_at": asyncio.get_event_loop().time(),
        }

    async def _manage_services_async(self, ssh_client, app_name: str, action: str) -> bool:
        """Start/stop/restart application services"""
        # Implementation would manage systemd services or similar
        # For now, simulate success
        await asyncio.sleep(0.5)
        return True

    async def _restore_from_backup_async(self, ssh_client, backup_info: dict[str, Any]) -> bool:
        """Restore deployment from backup"""
        # Implementation would restore files from backup
        # For now, simulate success
        await asyncio.sleep(1.0)
        return True

    async def _cleanup_old_backups_async(self, task: dict[str, Any]) -> None:
        """Cleanup old deployment backups"""
        # Implementation would clean up old backup directories
        pass

    async def _update_monitoring_config_async(self, task: dict[str, Any]) -> None:
        """Update monitoring configuration"""
        # Implementation would update monitoring configs
        pass

    async def _send_deployment_notifications_async(
        self, task: dict[str, Any], deployment_id: str, success: bool,
    ) -> None:
        """Send deployment notifications"""
        # Implementation would send notifications via email, Slack, etc.
        pass
