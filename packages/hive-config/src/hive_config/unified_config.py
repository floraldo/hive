"""
Unified Hive Configuration System
Provides centralized configuration management for all Hive components
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from pydantic import BaseModel, Field, ValidationError
import logging

logger = logging.getLogger(__name__)


class DatabaseConfig(BaseModel):
    """Database configuration settings"""
    path: Path = Field(default=Path("hive/db/hive-internal.db"))
    connection_pool_min: int = Field(default=2, ge=1)
    connection_pool_max: int = Field(default=10, ge=1)
    connection_timeout: int = Field(default=30, ge=1)
    max_retries: int = Field(default=3, ge=0)
    journal_mode: str = Field(default="WAL")
    synchronous: str = Field(default="NORMAL")
    cache_size: int = Field(default=10000)


class ClaudeConfig(BaseModel):
    """Claude API configuration settings"""
    mock_mode: bool = Field(default=False)
    timeout: int = Field(default=120, ge=1)
    max_retries: int = Field(default=3, ge=0)
    use_dangerously_skip_permissions: bool = Field(default=True)
    fallback_enabled: bool = Field(default=True)


class OrchestrationConfig(BaseModel):
    """Orchestration configuration settings"""
    poll_interval: int = Field(default=5, ge=1)
    worker_timeout: int = Field(default=600, ge=1)
    max_parallel_workers: int = Field(default=4, ge=1)
    phase_timeouts: Dict[str, int] = Field(default_factory=lambda: {
        "analysis": 300,
        "design": 600,
        "implementation": 900,
        "testing": 600,
        "validation": 300,
        "review": 180
    })
    zombie_task_threshold: int = Field(default=3600)
    heartbeat_interval: int = Field(default=30)


class WorkerConfig(BaseModel):
    """Worker configuration settings"""
    backend_enabled: bool = Field(default=True)
    frontend_enabled: bool = Field(default=True)
    infra_enabled: bool = Field(default=True)
    app_workers_enabled: bool = Field(default=True)
    max_retries_per_task: int = Field(default=3)
    output_capture: bool = Field(default=True)
    live_output: bool = Field(default=False)


class AIConfig(BaseModel):
    """AI component configuration settings"""
    planner_enabled: bool = Field(default=True)
    reviewer_enabled: bool = Field(default=True)
    planner_poll_interval: int = Field(default=10)
    reviewer_poll_interval: int = Field(default=15)
    auto_approval_threshold: int = Field(default=80)
    auto_rejection_threshold: int = Field(default=40)
    escalation_threshold: int = Field(default=60)


class LoggingConfig(BaseModel):
    """Logging configuration settings"""
    level: str = Field(default="INFO")
    format: str = Field(default="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    file_enabled: bool = Field(default=True)
    console_enabled: bool = Field(default=True)
    log_directory: Path = Field(default=Path("hive/logs"))
    max_file_size: int = Field(default=10485760)  # 10MB
    backup_count: int = Field(default=5)


class HiveConfig(BaseModel):
    """
    Unified Hive configuration

    This is the master configuration object that contains all settings
    for the entire Hive system.
    """
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    claude: ClaudeConfig = Field(default_factory=ClaudeConfig)
    orchestration: OrchestrationConfig = Field(default_factory=OrchestrationConfig)
    worker: WorkerConfig = Field(default_factory=WorkerConfig)
    ai: AIConfig = Field(default_factory=AIConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)

    # Environment settings
    environment: str = Field(default="development")
    debug_mode: bool = Field(default=False)

    # Project paths
    project_root: Optional[Path] = None
    config_file_path: Optional[Path] = None

    @classmethod
    def from_file(cls, config_path: Path) -> "HiveConfig":
        """
        Load configuration from a JSON file

        Args:
            config_path: Path to the configuration file

        Returns:
            HiveConfig instance
        """
        if not config_path.exists():
            logger.warning(f"Config file not found: {config_path}, using defaults")
            return cls()

        try:
            with open(config_path, 'r') as f:
                config_data = json.load(f)

            config = cls(**config_data)
            config.config_file_path = config_path
            return config

        except (json.JSONDecodeError, ValidationError) as e:
            logger.error(f"Failed to load config from {config_path}: {e}")
            logger.warning("Falling back to default configuration")
            return cls()

    @classmethod
    def from_environment(cls) -> "HiveConfig":
        """
        Load configuration from environment variables

        Environment variables should be prefixed with HIVE_
        e.g., HIVE_DATABASE_PATH, HIVE_CLAUDE_TIMEOUT, etc.

        Returns:
            HiveConfig instance
        """
        config_data = {}

        # Map environment variables to configuration structure
        env_mappings = {
            "HIVE_ENVIRONMENT": "environment",
            "HIVE_DEBUG_MODE": "debug_mode",
            "HIVE_DATABASE_PATH": "database.path",
            "HIVE_DATABASE_POOL_MIN": "database.connection_pool_min",
            "HIVE_DATABASE_POOL_MAX": "database.connection_pool_max",
            "HIVE_CLAUDE_MOCK_MODE": "claude.mock_mode",
            "HIVE_CLAUDE_TIMEOUT": "claude.timeout",
            "HIVE_WORKER_TIMEOUT": "orchestration.worker_timeout",
            "HIVE_POLL_INTERVAL": "orchestration.poll_interval",
            "HIVE_LOG_LEVEL": "logging.level",
            "HIVE_AI_PLANNER_ENABLED": "ai.planner_enabled",
            "HIVE_AI_REVIEWER_ENABLED": "ai.reviewer_enabled",
        }

        def set_nested(data: dict, path: str, value: Any):
            """Set a value in nested dictionary using dot notation"""
            keys = path.split('.')
            current = data
            for key in keys[:-1]:
                if key not in current:
                    current[key] = {}
                current = current[key]

            # Convert string values to appropriate types
            if value.lower() in ('true', 'false'):
                value = value.lower() == 'true'
            elif value.isdigit():
                value = int(value)

            current[keys[-1]] = value

        for env_var, config_path in env_mappings.items():
            value = os.environ.get(env_var)
            if value is not None:
                set_nested(config_data, config_path, value)

        try:
            return cls(**config_data)
        except ValidationError as e:
            logger.error(f"Invalid configuration from environment: {e}")
            return cls()

    def to_file(self, config_path: Path):
        """
        Save configuration to a JSON file

        Args:
            config_path: Path where to save the configuration
        """
        config_path.parent.mkdir(parents=True, exist_ok=True)

        with open(config_path, 'w') as f:
            json.dump(self.dict(), f, indent=2, default=str)

        logger.info(f"Configuration saved to {config_path}")

    def get_component_config(self, component: str) -> Dict[str, Any]:
        """
        Get configuration for a specific component

        Args:
            component: Component name (e.g., 'ai-planner', 'hive-orchestrator')

        Returns:
            Component-specific configuration dictionary
        """
        component_mappings = {
            "ai-planner": {
                "claude": self.claude.dict(),
                "database": self.database.dict(),
                "poll_interval": self.ai.planner_poll_interval,
                "enabled": self.ai.planner_enabled,
                "logging": self.logging.dict()
            },
            "ai-reviewer": {
                "claude": self.claude.dict(),
                "database": self.database.dict(),
                "poll_interval": self.ai.reviewer_poll_interval,
                "enabled": self.ai.reviewer_enabled,
                "thresholds": {
                    "approval": self.ai.auto_approval_threshold,
                    "rejection": self.ai.auto_rejection_threshold,
                    "escalation": self.ai.escalation_threshold
                },
                "logging": self.logging.dict()
            },
            "hive-orchestrator": {
                "database": self.database.dict(),
                "orchestration": self.orchestration.dict(),
                "worker": self.worker.dict(),
                "logging": self.logging.dict()
            }
        }

        return component_mappings.get(component, {})

    def validate(self) -> List[str]:
        """
        Validate the configuration

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        # Check pool size consistency
        if self.database.connection_pool_min > self.database.connection_pool_max:
            errors.append("Database min connections cannot be greater than max connections")

        # Check threshold consistency
        if self.ai.auto_approval_threshold <= self.ai.auto_rejection_threshold:
            errors.append("Approval threshold must be higher than rejection threshold")

        # Check file paths
        if self.database.path and not self.database.path.parent.exists():
            errors.append(f"Database directory does not exist: {self.database.path.parent}")

        # Check worker configuration
        if self.orchestration.max_parallel_workers < 1:
            errors.append("Must allow at least 1 parallel worker")

        return errors


# Global configuration instance
_config_instance: Optional[HiveConfig] = None


def load_config(
    config_path: Optional[Path] = None,
    use_environment: bool = True
) -> HiveConfig:
    """
    Load the global Hive configuration

    Args:
        config_path: Optional path to configuration file
        use_environment: Whether to override with environment variables

    Returns:
        HiveConfig instance
    """
    global _config_instance

    if _config_instance is None:
        # Try to load from file first
        if config_path and config_path.exists():
            _config_instance = HiveConfig.from_file(config_path)
        else:
            # Look for default config locations
            default_paths = [
                Path("hive_config.json"),
                Path("config/hive_config.json"),
                Path.home() / ".hive" / "config.json"
            ]

            for path in default_paths:
                if path.exists():
                    _config_instance = HiveConfig.from_file(path)
                    break
            else:
                _config_instance = HiveConfig()

        # Override with environment variables if requested
        if use_environment:
            env_config = HiveConfig.from_environment()
            # Merge environment config with file config
            for key, value in env_config.dict(exclude_unset=True).items():
                if value is not None:
                    setattr(_config_instance, key, value)

        # Validate configuration
        errors = _config_instance.validate()
        if errors:
            logger.warning(f"Configuration validation warnings: {errors}")

    return _config_instance


def get_config() -> Optional[HiveConfig]:
    """Get the global configuration instance"""
    return _config_instance


def reset_config():
    """Reset the global configuration (mainly for testing)"""
    global _config_instance
    _config_instance = None