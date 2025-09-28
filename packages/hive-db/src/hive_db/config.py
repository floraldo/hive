"""
Configuration utilities for Hive applications
"""

import os
from typing import Optional, Dict, Any
from dotenv import load_dotenv
from pathlib import Path

def load_hive_env():
    """Load Hive environment files in priority order"""
    hive_root = Path(__file__).parent.parent.parent.parent.parent

    # Load in priority order: shared -> global -> local
    env_files = [
        hive_root / '.env.shared',
        hive_root / '.env.global',
        hive_root / '.env'
    ]

    for env_file in env_files:
        if env_file.exists():
            load_dotenv(env_file, override=False)

# Load all environment configurations
load_hive_env()

class Config:
    """Configuration management for Hive applications."""

    # Default configuration values for all Hive components
    DEFAULTS = {
        # Environment
        "environment": "development",

        # Database
        "db_timeout": 30,
        "db_max_connections": 10,
        "db_connection_timeout": 5.0,

        # Claude Service
        "claude_rate_limit_per_minute": 30,
        "claude_rate_limit_per_hour": 1000,
        "claude_burst_size": 5,
        "claude_cache_ttl": 300,
        "claude_timeout": 120,
        "claude_max_retries": 3,
        "claude_mock_mode": False,

        # Orchestrator
        "worker_spawn_timeout": 30,
        "worker_init_timeout": 10,
        "worker_graceful_shutdown": 5,
        "status_refresh_seconds": 10,
        "heartbeat_interval": 30,
        "max_parallel_tasks": 5,
        "max_parallel_backend": 2,
        "max_parallel_frontend": 2,
        "max_parallel_infra": 1,

        # Logging
        "log_level": "INFO",
        "debug_mode": False,
        "verbose_logging": False,

        # Security
        "use_secure_connections": True,
        "api_key_rotation_days": 90,

        # Performance
        "enable_caching": True,
        "cache_cleanup_interval": 3600,  # 1 hour
        "metrics_retention_days": 30,
    }

    def __init__(self):
        self.env = os.environ.get('ENVIRONMENT', 'development')
        self._config_cache = {}
        self._load_defaults()

    def _load_defaults(self):
        """Load default configuration values"""
        self._config_cache = self.DEFAULTS.copy()

        # Override environment-specific defaults
        if self.is_production():
            self._config_cache.update({
                "log_level": "WARNING",
                "debug_mode": False,
                "claude_mock_mode": False,
                "use_secure_connections": True,
            })
        elif self.is_testing():
            self._config_cache.update({
                "log_level": "DEBUG",
                "debug_mode": True,
                "claude_mock_mode": True,
                "claude_rate_limit_per_minute": 1000,  # Higher limits for testing
                "db_timeout": 5,
            })

    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Get configuration value from environment with fallback to defaults."""
        # First check environment variables
        env_value = os.environ.get(key)
        if env_value is not None:
            return env_value

        # Then check cache/defaults
        cached_value = self._config_cache.get(key)
        if cached_value is not None:
            return str(cached_value)

        return default

    def get_int(self, key: str, default: int = 0) -> int:
        """Get integer configuration value."""
        try:
            value = self.get(key)
            return int(value) if value is not None else default
        except (ValueError, TypeError):
            return default

    def get_float(self, key: str, default: float = 0.0) -> float:
        """Get float configuration value."""
        try:
            value = self.get(key)
            return float(value) if value is not None else default
        except (ValueError, TypeError):
            return default

    def get_bool(self, key: str, default: bool = False) -> bool:
        """Get boolean configuration value."""
        value = self.get(key)
        if value is None:
            return default
        return str(value).lower() in ('true', '1', 'yes', 'on')

    def get_list(self, key: str, default: Optional[list] = None, separator: str = ',') -> list:
        """Get list configuration value from comma-separated string."""
        value = self.get(key)
        if value is None:
            return default or []
        return [item.strip() for item in value.split(separator) if item.strip()]

    def set(self, key: str, value: Any):
        """Set configuration value in cache."""
        self._config_cache[key] = value

    def get_all(self) -> Dict[str, Any]:
        """Get all configuration values."""
        return self._config_cache.copy()

    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.env == 'production'

    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.env == 'development'

    def is_testing(self) -> bool:
        """Check if running in testing environment."""
        return self.env == 'testing'

    def get_claude_config(self) -> Dict[str, Any]:
        """Get Claude service configuration."""
        return {
            "mock_mode": self.get_bool("claude_mock_mode"),
            "timeout": self.get_int("claude_timeout"),
            "max_retries": self.get_int("claude_max_retries"),
            "rate_limit_per_minute": self.get_int("claude_rate_limit_per_minute"),
            "rate_limit_per_hour": self.get_int("claude_rate_limit_per_hour"),
            "burst_size": self.get_int("claude_burst_size"),
            "cache_ttl": self.get_int("claude_cache_ttl"),
        }

    def get_database_config(self) -> Dict[str, Any]:
        """Get database configuration."""
        return {
            "timeout": self.get_int("db_timeout"),
            "max_connections": self.get_int("db_max_connections"),
            "connection_timeout": self.get_float("db_connection_timeout"),
        }

    def get_orchestrator_config(self) -> Dict[str, Any]:
        """Get orchestrator configuration."""
        return {
            "worker_spawn_timeout": self.get_int("worker_spawn_timeout"),
            "worker_init_timeout": self.get_int("worker_init_timeout"),
            "worker_graceful_shutdown": self.get_int("worker_graceful_shutdown"),
            "status_refresh_seconds": self.get_int("status_refresh_seconds"),
            "heartbeat_interval": self.get_int("heartbeat_interval"),
            "max_parallel_tasks": self.get_int("max_parallel_tasks"),
            "max_parallel_per_role": {
                "backend": self.get_int("max_parallel_backend"),
                "frontend": self.get_int("max_parallel_frontend"),
                "infra": self.get_int("max_parallel_infra"),
            },
            "debug_mode": self.get_bool("debug_mode"),
            "verbose_logging": self.get_bool("verbose_logging"),
        }

    def get_logging_config(self) -> Dict[str, Any]:
        """Get logging configuration."""
        return {
            "level": self.get("log_level"),
            "debug_mode": self.get_bool("debug_mode"),
            "verbose": self.get_bool("verbose_logging"),
        }

# Global configuration instance
config = Config()

def get_config() -> Config:
    """Get the global configuration instance."""
    return config