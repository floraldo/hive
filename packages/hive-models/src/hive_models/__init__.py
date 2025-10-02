"""
Hive Models - Shared data models for the Hive platform.

This package provides centralized data models used across multiple Hive applications,
ensuring consistent data structures and clean dependency management.
"""

from .base import BaseModel, IdentifiableMixin, MetadataMixin, StatusMixin, TimestampMixin
from .common import Environment, ExecutionResult, HealthStatus, Priority, ResourceMetrics, Status

# Import from domain-specific modules as they're created
# from .deployment import DeploymentTask, DeploymentConfig, DeploymentStatus
# from .review import ReviewRequest, ReviewResult, CodeQualityMetrics
# from .planning import PlanningTask, TaskDependency, TaskStatus
# from .orchestration import WorkflowStep, WorkflowStatus, WorkerConfig
# from .climate import ClimateData, LocationData, TimeRange

__version__ = ("1.0.0",)

__all__ = [
    # Base models and mixins
    "BaseModel",
    "TimestampMixin",
    "IdentifiableMixin",
    "StatusMixin",
    "MetadataMixin",
    # Common models
    "Status",
    "Priority",
    "Environment",
    "ExecutionResult",
    "ResourceMetrics",
    "HealthStatus",
]
