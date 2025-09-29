from hive_logging import get_logger

logger = get_logger(__name__)

"""
Deployment strategies for various platforms and environments
"""

from .base import BaseDeploymentStrategy
from .docker import DockerDeploymentStrategy
from .kubernetes import KubernetesDeploymentStrategy
from .ssh import SSHDeploymentStrategy

__all__ = [
    "BaseDeploymentStrategy",
    "SSHDeploymentStrategy",
    "DockerDeploymentStrategy",
    "KubernetesDeploymentStrategy",
]
