"""
Configuration module for Hive Orchestrator.
Centralizes configuration with environment variable support.
"""

import os
from pathlib import Path
from typing import Dict, Any

class HiveConfig:
    """Configuration management for Hive Orchestrator"""

    # Default configuration values
    DEFAULTS = {
        # Worker spawning
        "worker_spawn_timeout": 30,  # seconds
        "worker_init_timeout": 10,   # seconds to wait for worker initialization
        "worker_graceful_shutdown": 5,  # seconds to wait for graceful shutdown

        # Monitoring
        "status_refresh_seconds": 10,
        "heartbeat_interval": 30,

        # Execution limits
        "max_parallel_tasks": 5,
        "max_parallel_per_role": {
            "backend": 2,
            "frontend": 2,
            "infra": 1
        },

        # Windows-specific
        "windows_use_devnull": True,  # Use DEVNULL for stdout on Windows
        "windows_capture_stderr": True,  # Capture stderr for error debugging

        # Paths
        "python_executable": os.environ.get("HIVE_PYTHON", os.sys.executable),

        # Debug
        "debug_mode": os.environ.get("HIVE_DEBUG", "false").lower() == "true",
        "verbose_logging": os.environ.get("HIVE_VERBOSE", "false").lower() == "true"
    }

    def __init__(self):
        """Initialize configuration with defaults and environment overrides"""
        self.config = self.DEFAULTS.copy()
        self._load_environment_overrides()

    def _load_environment_overrides(self):
        """Load configuration from environment variables"""
        # Numeric overrides
        if "HIVE_WORKER_SPAWN_TIMEOUT" in os.environ:
            self.config["worker_spawn_timeout"] = int(os.environ["HIVE_WORKER_SPAWN_TIMEOUT"])

        if "HIVE_WORKER_INIT_TIMEOUT" in os.environ:
            self.config["worker_init_timeout"] = int(os.environ["HIVE_WORKER_INIT_TIMEOUT"])

        if "HIVE_STATUS_REFRESH" in os.environ:
            self.config["status_refresh_seconds"] = int(os.environ["HIVE_STATUS_REFRESH"])

        if "HIVE_MAX_PARALLEL" in os.environ:
            self.config["max_parallel_tasks"] = int(os.environ["HIVE_MAX_PARALLEL"])

        # Boolean overrides
        if "HIVE_WINDOWS_DEVNULL" in os.environ:
            self.config["windows_use_devnull"] = os.environ["HIVE_WINDOWS_DEVNULL"].lower() == "true"

        if "HIVE_WINDOWS_STDERR" in os.environ:
            self.config["windows_capture_stderr"] = os.environ["HIVE_WINDOWS_STDERR"].lower() == "true"

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value"""
        return self.config.get(key, default)

    def set(self, key: str, value: Any):
        """Set configuration value"""
        self.config[key] = value

    def get_all(self) -> Dict[str, Any]:
        """Get all configuration values"""
        return self.config.copy()

    def is_debug(self) -> bool:
        """Check if debug mode is enabled"""
        return self.config.get("debug_mode", False)

    def is_verbose(self) -> bool:
        """Check if verbose logging is enabled"""
        return self.config.get("verbose_logging", False)

    def get_worker_config(self, worker_type: str) -> Dict[str, Any]:
        """Get configuration specific to a worker type"""
        return {
            "max_parallel": self.config["max_parallel_per_role"].get(worker_type, 1),
            "spawn_timeout": self.config["worker_spawn_timeout"],
            "init_timeout": self.config["worker_init_timeout"],
            "graceful_shutdown": self.config["worker_graceful_shutdown"]
        }


# Global config instance
_config = None

def get_config() -> HiveConfig:
    """Get global configuration instance"""
    global _config
    if _config is None:
        _config = HiveConfig()
    return _config