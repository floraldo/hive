"""
Common shared models used across multiple Hive applications.

These models represent common concepts and data structures that are
used throughout the platform.
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from datetime import datetime

from pydantic import Field, field_validator

from .base import BaseModel, TimestampMixin


class Status(str, Enum):
    """Common status values used across the platform."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"
    QUEUED = "queued"
    RETRYING = "retrying"


class Priority(str, Enum):
    """Priority levels for tasks and operations."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    TRIVIAL = "trivial"


class Environment(str, Enum):
    """Deployment environment types."""

    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"
    DISASTER_RECOVERY = "disaster_recovery"


class ExecutionResult(BaseModel):
    """Result of executing an operation or task."""

    success: bool = Field(description="Whether the execution succeeded")
    message: Optional[str] = Field(
        default=None,
        description="Human-readable message about the execution"
    )
    data: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Any data returned from the execution"
    )
    error: Optional[str] = Field(
        default=None,
        description="Error message if execution failed"
    )
    error_details: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Detailed error information for debugging"
    )
    duration_ms: Optional[float] = Field(
        default=None,
        description="Execution duration in milliseconds"
    )

    @field_validator('error')
    def validate_error_consistency(cls, v: Optional[str], values: Dict[str, Any]) -> Optional[str]:
        """Ensure error is only set when success is False."""
        if v and values.get('success', True):
            raise ValueError("Error cannot be set when success is True")
        return v


class ResourceMetrics(BaseModel):
    """Metrics for resource usage and performance."""

    cpu_percent: float = Field(
        ge=0, le=100,
        description="CPU usage percentage"
    )
    memory_mb: float = Field(
        ge=0,
        description="Memory usage in megabytes"
    )
    memory_percent: float = Field(
        ge=0, le=100,
        description="Memory usage percentage"
    )
    disk_io_read_mb: Optional[float] = Field(
        default=None, ge=0,
        description="Disk I/O read in megabytes"
    )
    disk_io_write_mb: Optional[float] = Field(
        default=None, ge=0,
        description="Disk I/O write in megabytes"
    )
    network_sent_mb: Optional[float] = Field(
        default=None, ge=0,
        description="Network data sent in megabytes"
    )
    network_recv_mb: Optional[float] = Field(
        default=None, ge=0,
        description="Network data received in megabytes"
    )
    open_connections: Optional[int] = Field(
        default=None, ge=0,
        description="Number of open network connections"
    )
    thread_count: Optional[int] = Field(
        default=None, ge=0,
        description="Number of active threads"
    )


class HealthStatus(BaseModel, TimestampMixin):
    """Health status for services and components."""

    component: str = Field(description="Name of the component or service")
    healthy: bool = Field(description="Whether the component is healthy")
    status: Status = Field(
        default=Status.PENDING,
        description="Current status of the component"
    )
    message: Optional[str] = Field(
        default=None,
        description="Additional health information"
    )
    checks: Dict[str, bool] = Field(
        default_factory=dict,
        description="Individual health check results"
    )
    metrics: Optional[ResourceMetrics] = Field(
        default=None,
        description="Resource usage metrics"
    )
    last_check: datetime = Field(
        default_factory=datetime.utcnow,
        description="When health was last checked"
    )

    @property
    def is_degraded(self) -> bool:
        """Check if component is in degraded state."""
        return not self.healthy and self.status != Status.FAILED

    @property
    def all_checks_passing(self) -> bool:
        """Check if all individual health checks are passing."""
        return all(self.checks.values()) if self.checks else True


class Configuration(BaseModel):
    """Generic configuration container."""

    name: str = Field(description="Configuration name or identifier")
    version: str = Field(default="1.0.0", description="Configuration version")
    values: Dict[str, Any] = Field(
        default_factory=dict,
        description="Configuration key-value pairs"
    )
    environment: Optional[Environment] = Field(
        default=None,
        description="Target environment for this configuration"
    )
    encrypted_values: List[str] = Field(
        default_factory=list,
        description="List of keys that contain encrypted values"
    )

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value with optional default."""
        return self.values.get(key, default)

    def set(self, key: str, value: Any, encrypted: bool = False) -> None:
        """Set configuration value, optionally marking as encrypted."""
        self.values[key] = value
        if encrypted and key not in self.encrypted_values:
            self.encrypted_values.append(key)

    def is_encrypted(self, key: str) -> bool:
        """Check if a configuration key contains encrypted data."""
        return key in self.encrypted_values