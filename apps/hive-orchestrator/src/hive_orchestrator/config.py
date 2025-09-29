from hive_logging import get_logger

logger = get_logger(__name__)

"""
Configuration module for Hive Orchestrator.
Centralizes configuration with environment variable support.
"""

import sys
from typing import Any


class HiveConfig:
    """Configuration management for Hive Orchestrator with DI support"""

    # Default configuration values
    DEFAULTS = {
        # Worker spawning
        "worker_spawn_timeout": 30,  # seconds,
        "worker_init_timeout": 10,  # seconds to wait for worker initialization,
        "worker_graceful_shutdown": 5,  # seconds to wait for graceful shutdown
        # Monitoring
        "status_refresh_seconds": 10,
        "heartbeat_interval": 30,
        # Execution limits
        "max_parallel_tasks": 5,
        "max_parallel_per_role": {"backend": 2, "frontend": 2, "infra": 1},
        # Windows-specific
        "windows_use_devnull": True,  # Use DEVNULL for stdout on Windows
        "windows_capture_stderr": True,  # Capture stderr for error debugging
        # Paths
        "python_executable": sys.executable,
        # Debug
        "debug_mode": False,
        "verbose_logging": False,
    }

    def __init__(self, env_vars: dict[str, str] | None = None) -> None:
        """Initialize configuration with defaults and optional environment overrides

        Args:
            env_vars: Optional dictionary of environment variables for DI.
                     If None, configuration uses defaults only.
        """
        self.config = self.DEFAULTS.copy()
        if env_vars:
            self._load_environment_overrides(env_vars)

    def _load_environment_overrides(self, env_vars: dict[str, str]) -> None:
        """Load configuration from provided environment variables

        Args:
            env_vars: Dictionary of environment variables
        """
        # Numeric overrides
        if "HIVE_WORKER_SPAWN_TIMEOUT" in env_vars:
            self.config["worker_spawn_timeout"] = int(env_vars["HIVE_WORKER_SPAWN_TIMEOUT"])

        if "HIVE_WORKER_INIT_TIMEOUT" in env_vars:
            self.config["worker_init_timeout"] = int(env_vars["HIVE_WORKER_INIT_TIMEOUT"])

        if "HIVE_STATUS_REFRESH" in env_vars:
            self.config["status_refresh_seconds"] = int(env_vars["HIVE_STATUS_REFRESH"])

        if "HIVE_MAX_PARALLEL" in env_vars:
            self.config["max_parallel_tasks"] = int(env_vars["HIVE_MAX_PARALLEL"])

        # Boolean overrides
        if "HIVE_WINDOWS_DEVNULL" in env_vars:
            self.config["windows_use_devnull"] = env_vars["HIVE_WINDOWS_DEVNULL"].lower() == "true"

        if "HIVE_WINDOWS_STDERR" in env_vars:
            self.config["windows_capture_stderr"] = env_vars["HIVE_WINDOWS_STDERR"].lower() == "true"

        # Path overrides
        if "HIVE_PYTHON" in env_vars:
            self.config["python_executable"] = env_vars["HIVE_PYTHON"]

        # Debug overrides
        if "HIVE_DEBUG" in env_vars:
            self.config["debug_mode"] = env_vars["HIVE_DEBUG"].lower() == "true"

        if "HIVE_VERBOSE" in env_vars:
            self.config["verbose_logging"] = env_vars["HIVE_VERBOSE"].lower() == "true"

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value"""
        return self.config.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set configuration value"""
        self.config[key] = value

    def get_all(self) -> dict[str, Any]:
        """Get all configuration values"""
        return self.config.copy()

    def is_debug(self) -> bool:
        """Check if debug mode is enabled"""
        return self.config.get("debug_mode", False)

    def is_verbose(self) -> bool:
        """Check if verbose logging is enabled"""
        return self.config.get("verbose_logging", False)

    def get_worker_config(self, worker_type: str) -> dict[str, Any]:
        """Get configuration specific to a worker type"""
        return {
            "max_parallel": self.config["max_parallel_per_role"].get(worker_type, 1),
            "spawn_timeout": self.config["worker_spawn_timeout"],
            "init_timeout": self.config["worker_init_timeout"],
            "graceful_shutdown": self.config["worker_graceful_shutdown"],
        }

    def get_database_config(self) -> dict[str, Any]:
        """Get database configuration for compatibility"""
        return {"max_connections": 25, "connection_timeout": 30.0, "min_connections": 3}

    def get_claude_config(self) -> dict[str, Any]:
        """Get Claude configuration for compatibility"""
        return {
            "mock_mode": False,
            "timeout": 30,
            "max_retries": 3,
            "rate_limit_per_minute": 10,
            "rate_limit_per_hour": 100,
            "burst_size": 5,
            "cache_ttl": 300,
        }


def create_orchestrator_config(env_vars: dict[str, str] | None = None) -> HiveConfig:
    """Create a new orchestrator configuration instance

    This replaces the global singleton pattern with explicit creation.
    Call this once at application startup and pass the config down.

    Args:
        env_vars: Optional dictionary of environment variables for DI.
                 If None, configuration uses defaults only.
                 In production, pass os.environ.copy() here.

    Example:
        # Production with environment variables
        import os
        config = create_orchestrator_config(os.environ.copy())

        # Testing with custom config
        config = create_orchestrator_config({"HIVE_DEBUG": "true"})

        # Testing with defaults only
        config = create_orchestrator_config()
    """
    return HiveConfig(env_vars)
