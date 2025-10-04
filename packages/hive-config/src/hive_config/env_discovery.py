"""
Dynamic Environment Variable Discovery

Auto-discovers and maps HIVE_* environment variables to HiveConfig structure
without requiring manual mapping maintenance.

This eliminates the hardcoded env_mappings dictionary in unified_config.py.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from hive_logging import get_logger

logger = get_logger(__name__)


def discover_hive_env_vars() -> dict[str, Any]:
    """
    Auto-discover all HIVE_* environment variables and map to config structure.

    Supports nested paths using underscores:
    - HIVE_DATABASE_PATH → database.path
    - HIVE_CLAUDE_TIMEOUT → claude.timeout
    - HIVE_CACHE_REDIS_URL → cache.redis_url (for future use)

    Returns:
        Dictionary with nested structure matching HiveConfig
    """
    env_data = {}

    # Find all HIVE_* environment variables
    hive_vars = {k: v for k, v in os.environ.items() if k.startswith("HIVE_")}

    logger.debug(f"Found {len(hive_vars)} HIVE_* environment variables")

    for env_var, value in hive_vars.items():
        # Remove HIVE_ prefix and convert to lowercase
        key_path = env_var[5:].lower()

        # Map common patterns to config structure
        mapped_path = _map_env_var_to_config_path(key_path, value)

        if mapped_path:
            _set_nested_value(env_data, mapped_path, value)
            logger.debug(f"Mapped {env_var} → {mapped_path}")

    return env_data


def _map_env_var_to_config_path(key_path: str, value: str) -> str | None:
    """
    Map environment variable key to HiveConfig attribute path.

    Args:
        key_path: Lowercase environment variable name (without HIVE_ prefix)
        value: Environment variable value

    Returns:
        Dotted path in HiveConfig structure, or None if unmapped
    """
    # Direct mappings (high-level config)
    if key_path == "environment":
        return "environment"
    if key_path == "debug_mode":
        return "debug_mode"

    # Database configuration
    if key_path.startswith("database_") or key_path.startswith("db_"):
        return _map_database_var(key_path)

    # Claude configuration
    if key_path.startswith("claude_"):
        return _map_claude_var(key_path)

    # Orchestration configuration
    if key_path.startswith("orchestration_") or key_path in ("worker_timeout", "poll_interval"):
        return _map_orchestration_var(key_path)

    # Worker configuration
    if key_path.startswith("worker_"):
        return _map_worker_var(key_path)

    # AI configuration
    if key_path.startswith("ai_"):
        return _map_ai_var(key_path)

    # Logging configuration
    if key_path.startswith("log_") or key_path.startswith("logging_"):
        return _map_logging_var(key_path)

    # Cache configuration (for future use)
    if key_path.startswith("cache_"):
        return _map_cache_var(key_path)

    logger.debug(f"No mapping found for HIVE_{key_path.upper()}")
    return None


def _map_database_var(key_path: str) -> str:
    """Map database-related environment variables."""
    # Remove database_ or db_ prefix
    key = key_path.replace("database_", "").replace("db_", "")

    mappings = {
        "path": "database.path",
        "pool_min": "database.connection_pool_min",
        "pool_max": "database.connection_pool_max",
        "connection_pool_min": "database.connection_pool_min",
        "connection_pool_max": "database.connection_pool_max",
        "timeout": "database.connection_timeout",
        "connection_timeout": "database.connection_timeout",
        "max_retries": "database.max_retries",
        "journal_mode": "database.journal_mode",
        "synchronous": "database.synchronous",
        "cache_size": "database.cache_size",
    }

    return mappings.get(key, f"database.{key}")


def _map_claude_var(key_path: str) -> str:
    """Map Claude-related environment variables."""
    key = key_path.replace("claude_", "")

    mappings = {
        "mock_mode": "claude.mock_mode",
        "timeout": "claude.timeout",
        "max_retries": "claude.max_retries",
        "use_dangerously_skip_permissions": "claude.use_dangerously_skip_permissions",
        "fallback_enabled": "claude.fallback_enabled",
    }

    return mappings.get(key, f"claude.{key}")


def _map_orchestration_var(key_path: str) -> str:
    """Map orchestration-related environment variables."""
    key = key_path.replace("orchestration_", "")

    mappings = {
        "poll_interval": "orchestration.poll_interval",
        "worker_timeout": "orchestration.worker_timeout",
        "max_parallel_workers": "orchestration.max_parallel_workers",
        "heartbeat_interval": "orchestration.heartbeat_interval",
        "zombie_task_threshold": "orchestration.zombie_task_threshold",
    }

    return mappings.get(key, f"orchestration.{key}")


def _map_worker_var(key_path: str) -> str:
    """Map worker-related environment variables."""
    key = key_path.replace("worker_", "")

    mappings = {
        "backend_enabled": "worker.backend_enabled",
        "frontend_enabled": "worker.frontend_enabled",
        "infra_enabled": "worker.infra_enabled",
        "app_workers_enabled": "worker.app_workers_enabled",
        "max_retries_per_task": "worker.max_retries_per_task",
        "output_capture": "worker.output_capture",
        "live_output": "worker.live_output",
    }

    return mappings.get(key, f"worker.{key}")


def _map_ai_var(key_path: str) -> str:
    """Map AI-related environment variables."""
    key = key_path.replace("ai_", "")

    mappings = {
        "planner_enabled": "ai.planner_enabled",
        "reviewer_enabled": "ai.reviewer_enabled",
        "planner_poll_interval": "ai.planner_poll_interval",
        "reviewer_poll_interval": "ai.reviewer_poll_interval",
        "auto_approval_threshold": "ai.auto_approval_threshold",
        "auto_rejection_threshold": "ai.auto_rejection_threshold",
        "escalation_threshold": "ai.escalation_threshold",
    }

    return mappings.get(key, f"ai.{key}")


def _map_logging_var(key_path: str) -> str:
    """Map logging-related environment variables."""
    key = key_path.replace("logging_", "").replace("log_", "")

    mappings = {
        "level": "logging.level",
        "format": "logging.format",
        "file_enabled": "logging.file_enabled",
        "console_enabled": "logging.console_enabled",
        "directory": "logging.log_directory",
        "log_directory": "logging.log_directory",
        "max_file_size": "logging.max_file_size",
        "backup_count": "logging.backup_count",
    }

    return mappings.get(key, f"logging.{key}")


def _map_cache_var(key_path: str) -> str:
    """Map cache-related environment variables (for future use)."""
    key = key_path.replace("cache_", "")

    # This will be used when we add CacheConfig to HiveConfig
    mappings = {
        "redis_url": "cache.redis_url",
        "max_connections": "cache.max_connections",
        "default_ttl": "cache.default_ttl",
        "enabled": "cache.enabled",
    }

    return mappings.get(key, f"cache.{key}")


def _set_nested_value(data: dict, path: str, value: str) -> None:
    """
    Set a value in nested dictionary using dot notation.

    Args:
        data: Dictionary to update
        path: Dot-separated path (e.g., "database.path")
        value: String value to set (will be type-converted)
    """
    keys = path.split(".")
    current = data

    # Navigate to parent dict
    for key in keys[:-1]:
        if key not in current:
            current[key] = {}
        current = current[key]

    # Set the value with type conversion
    final_key = keys[-1]
    current[final_key] = _convert_value_type(value, final_key)


def _convert_value_type(value: str, key: str) -> Any:
    """
    Convert string value to appropriate Python type.

    Args:
        value: String value from environment
        key: Key name (used for type hints)

    Returns:
        Converted value (bool, int, Path, or str)
    """
    # Boolean conversion
    if value.lower() in ("true", "false", "yes", "no", "1", "0"):
        return value.lower() in ("true", "yes", "1")

    # Integer conversion
    if value.isdigit() or (value.startswith("-") and value[1:].isdigit()):
        return int(value)

    # Float conversion
    try:
        if "." in value:
            return float(value)
    except ValueError:
        pass

    # Path conversion for known path fields
    if "path" in key.lower() or "dir" in key.lower():
        return Path(value)

    # Default: return as string
    return value


def get_env_config_dict() -> dict[str, Any]:
    """
    Get configuration dictionary from environment variables.

    This is the main entry point for environment variable discovery.

    Returns:
        Nested dictionary matching HiveConfig structure
    """
    return discover_hive_env_vars()
