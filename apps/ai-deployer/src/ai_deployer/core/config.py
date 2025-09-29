from hive_logging import get_logger

logger = get_logger(__name__)

"""
AI Deployer Configuration Management.

Extends hive-config with deployer-specific settings following the inherit→extend pattern.
"""

from typing import Dict, List, Optional

try:
    from hive_config import HiveConfig
    from hive_config import load_config as load_hive_config
except ImportError:
    # Fallback for development - define minimal config structure
    from pydantic import BaseModel

    class HiveConfig(BaseModel):
        """Minimal hive config for fallback"""

        pass

    def load_hive_config() -> HiveConfig:
        """Fallback config loader"""
        return HiveConfig()


from pydantic import BaseModel, Field


class SSHDeploymentConfig(BaseModel):
    """SSH deployment strategy configuration"""

    default_user: str = "deploy"
    default_port: int = 22
    key_path: Optional[str] = None
    timeout_seconds: int = 300
    retry_attempts: int = 3


class DockerDeploymentConfig(BaseModel):
    """Docker deployment strategy configuration"""

    registry_url: Optional[str] = None
    default_tag: str = "latest"
    health_check_timeout: int = 60
    rollback_on_failure: bool = True


class KubernetesDeploymentConfig(BaseModel):
    """Kubernetes deployment strategy configuration"""

    namespace: str = "default"
    kubeconfig_path: Optional[str] = None
    canary_percentage: int = 10
    promotion_timeout: int = 300


class DeploymentConfig(BaseModel):
    """Deployment-specific configuration"""

    default_strategy: str = "ssh"
    max_concurrent_deployments: int = 3
    deployment_timeout_minutes: int = 30
    enable_rollback: bool = True
    notification_webhooks: List[str] = Field(default_factory=list)

    # Strategy-specific configs
    ssh: SSHDeploymentConfig = SSHDeploymentConfig()
    docker: DockerDeploymentConfig = DockerDeploymentConfig()
    kubernetes: KubernetesDeploymentConfig = KubernetesDeploymentConfig()


class AIDeployerConfig(HiveConfig):
    """Extended configuration for AI Deployer"""

    deployment: DeploymentConfig = DeploymentConfig()


def load_config() -> AIDeployerConfig:
    """
    Load AI Deployer configuration extending hive config.

    Returns:
        AIDeployerConfig: Complete configuration with hive base + deployer extensions
    """
    # Load base hive configuration
    hive_config = load_hive_config()

    # Merge with deployer-specific config
    return AIDeployerConfig(**hive_config.dict(), deployment=DeploymentConfig())


# Convenience function for getting specific deployment config
def get_deployment_config() -> DeploymentConfig:
    """Get deployment-specific configuration"""

    return config.deployment
