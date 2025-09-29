from hive_logging import get_logger

logger = get_logger(__name__)

"""
AI Deployer - Autonomous deployment agent for Hive platform

This agent monitors the deployment_pending queue and automatically deploys
approved applications using various deployment strategies.
"""

from .agent import DeploymentAgent
from .database_adapter import DatabaseAdapter
from .deployer import DeploymentOrchestrator

__version__ = "0.1.0"

__all__ = [
    "DeploymentAgent",
    "DeploymentOrchestrator",
    "DatabaseAdapter",
]
