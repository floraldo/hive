"""Package Defaults Discovery for Unified Configuration System

This module implements Layer 1 of the unified configuration hierarchy:
discovering and loading config.defaults.toml files from installed hive-* packages.

Packages remain passive - they NEVER read these files. The config system loads them.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

try:
    import tomli
except ImportError:
    import tomllib as tomli  # Python 3.11+

from hive_logging import get_logger

logger = get_logger(__name__)


def discover_package_defaults() -> dict[str, Any]:
    """Discover and load package-level config.defaults.toml files.

    This implements Layer 1 of the unified configuration hierarchy.
    Package defaults are passively loaded by the config system, packages
    never read these files directly.

    Returns:
        Merged configuration from all discovered package defaults

    """
    package_config = {}

    try:
        # Find all installed hive-* packages
        hive_packages = [
            name for name in sys.modules.keys()
            if name.startswith("hive_") and "." not in name
        ]

        logger.debug(f"Scanning {len(hive_packages)} hive packages for defaults")

        for pkg_name in hive_packages:
            try:
                # Get package location
                spec = importlib.util.find_spec(pkg_name)
                if not spec or not spec.origin:
                    continue

                pkg_path = Path(spec.origin).parent
                defaults_file = pkg_path / "config.defaults.toml"

                if defaults_file.exists():
                    with open(defaults_file, "rb") as f:
                        pkg_defaults = tomli.load(f)

                    # Merge package defaults (later packages can override earlier ones)
                    deep_merge(package_config, pkg_defaults)

                    logger.debug(f"Loaded package defaults from {pkg_name}: {defaults_file}")

            except Exception as e:
                logger.warning(f"Failed to load package defaults for {pkg_name}: {e}")
                continue

    except Exception as e:
        logger.warning(f"Failed to discover package defaults: {e}")

    return package_config


def deep_merge(base: dict, override: dict) -> None:
    """Deep merge override dict into base dict.

    Args:
        base: Base dictionary to merge into (modified in place)
        override: Override dictionary with new values

    """
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            deep_merge(base[key], value)
        else:
            base[key] = value


def map_package_defaults_to_hive_config(package_defaults: dict) -> dict[str, Any]:
    """Map package defaults structure to HiveConfig structure.

    Package defaults use package-specific namespacing, we need to
    map them to the unified HiveConfig structure.

    Args:
        package_defaults: Raw package defaults

    Returns:
        Configuration dict mapped to HiveConfig structure

    """
    mapped_config = {}

    # Map known package defaults to HiveConfig fields
    # Database config from hive-db
    if "connection" in package_defaults or "pool" in package_defaults or "sqlite" in package_defaults:
        db_config = {}

        if "pool" in package_defaults:
            db_config["connection_pool_min"] = package_defaults["pool"].get("min_connections", 2)
            db_config["connection_pool_max"] = package_defaults["pool"].get("max_connections", 10)
            db_config["connection_timeout"] = package_defaults["pool"].get("connection_timeout", 30)
            db_config["max_retries"] = package_defaults["pool"].get("max_retries", 3)

        if "sqlite" in package_defaults:
            db_config["journal_mode"] = package_defaults["sqlite"].get("journal_mode", "WAL")
            db_config["synchronous"] = package_defaults["sqlite"].get("synchronous", "NORMAL")
            db_config["cache_size"] = package_defaults["sqlite"].get("cache_size", 10000)

        if db_config:
            mapped_config["database"] = db_config

    # Claude config from hive-ai
    if "claude" in package_defaults:
        claude_config = {}
        claude_defaults = package_defaults["claude"]

        claude_config["mock_mode"] = claude_defaults.get("mock_mode", False)
        claude_config["timeout"] = claude_defaults.get("timeout", 120)
        claude_config["max_retries"] = claude_defaults.get("max_retries", 3)
        claude_config["use_dangerously_skip_permissions"] = claude_defaults.get(
            "use_dangerously_skip_permissions", True,
        )
        claude_config["fallback_enabled"] = claude_defaults.get("fallback_enabled", True)

        mapped_config["claude"] = claude_config

    # Orchestration config from hive-orchestration
    if "orchestration" in package_defaults:
        orch_config = {}
        orch_defaults = package_defaults["orchestration"]

        orch_config["poll_interval"] = orch_defaults.get("poll_interval", 5)
        orch_config["worker_timeout"] = orch_defaults.get("worker_timeout", 600)
        orch_config["max_parallel_workers"] = orch_defaults.get("max_parallel_workers", 4)
        orch_config["heartbeat_interval"] = orch_defaults.get("heartbeat_interval", 30)
        orch_config["zombie_task_threshold"] = orch_defaults.get("zombie_task_threshold", 3600)

        if "phase_timeouts" in package_defaults:
            orch_config["phase_timeouts"] = package_defaults["phase_timeouts"]

        mapped_config["orchestration"] = orch_config

    # Worker config from hive-orchestration
    if "worker" in package_defaults:
        worker_config = {}
        worker_defaults = package_defaults["worker"]

        worker_config["backend_enabled"] = worker_defaults.get("backend_enabled", True)
        worker_config["frontend_enabled"] = worker_defaults.get("frontend_enabled", True)
        worker_config["infra_enabled"] = worker_defaults.get("infra_enabled", True)
        worker_config["app_workers_enabled"] = worker_defaults.get("app_workers_enabled", True)
        worker_config["max_retries_per_task"] = worker_defaults.get("max_retries_per_task", 3)
        worker_config["output_capture"] = worker_defaults.get("output_capture", True)
        worker_config["live_output"] = worker_defaults.get("live_output", False)

        mapped_config["worker"] = worker_config

    # Logging config from hive-logging
    if "logging" in package_defaults or "file" in package_defaults or "console" in package_defaults:
        log_config = {}

        if "logging" in package_defaults:
            log_defaults = package_defaults["logging"]
            log_config["level"] = log_defaults.get("level", "INFO")
            log_config["format"] = log_defaults.get("format", "%(asctime)s - %(name)s - %(levelname)s - %(message)s")

        if "file" in package_defaults:
            file_defaults = package_defaults["file"]
            log_config["file_enabled"] = file_defaults.get("enabled", True)
            log_config["log_directory"] = Path(file_defaults.get("directory", "hive/logs"))
            log_config["max_file_size"] = file_defaults.get("max_file_size", 10485760)
            log_config["backup_count"] = file_defaults.get("backup_count", 5)

        if "console" in package_defaults:
            console_defaults = package_defaults["console"]
            log_config["console_enabled"] = console_defaults.get("enabled", True)

        if log_config:
            mapped_config["logging"] = log_config

    return mapped_config
