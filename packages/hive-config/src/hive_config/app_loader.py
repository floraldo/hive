"""
Unified App Configuration Loader

This module provides the load_config_for_app() function which is the
recommended entry point for all Hive applications.

It combines:
- Layer 1: Package defaults (config.defaults.toml from hive-* packages)
- Layer 2: App .env files (.env.global → .env.shared → apps/{app}/.env)
- Layer 3: User config files (hive_config.json, config.toml)
- Layer 4: Environment variables (HIVE_* prefixed)
"""

from __future__ import annotations

from pathlib import Path

from hive_logging import get_logger

from .loader import load_config_for_app as load_env_config
from .unified_config import HiveConfig, create_config_from_sources

logger = get_logger(__name__)


def load_config_for_app(
    app_name: str,
    app_root: Path | None = None,
    config_path: Path | None = None,
    use_package_defaults: bool = True,
    use_env_files: bool = True,
    use_environment: bool = True,
) -> HiveConfig:
    """
    Unified configuration loader for Hive applications.

    This is the ONE function apps should call to get their configuration.
    It replaces manual config creation and environment loading.

    Configuration hierarchy (lowest to highest precedence):
    1. Package defaults (config.defaults.toml in hive-* packages)
    2. App .env files (.env.global → .env.shared → apps/{app}/.env)
    3. User config file (hive_config.json or app-specific config.toml)
    4. Environment variables (HIVE_* prefixed)

    Args:
        app_name: Name of the application (e.g., "ai-planner", "ecosystemiser")
        app_root: Root directory of the app (defaults to apps/{app_name})
        config_path: Optional path to app-specific config file
        use_package_defaults: Load package-level defaults (Layer 1)
        use_env_files: Load .env files hierarchy (Layer 2)
        use_environment: Load environment variables (Layer 4)

    Returns:
        HiveConfig instance with all layers merged

    Example:
        >>> from hive_config import load_config_for_app
        >>>
        >>> # In apps/ai-planner/main.py
        >>> config = load_config_for_app("ai-planner")
        >>> db_path = config.database.path
        >>> claude_timeout = config.claude.timeout
    """
    # Start with base config from unified sources (Layers 1, 3, 4)
    config = create_config_from_sources(
        config_path=config_path,
        use_environment=use_environment,
        use_package_defaults=use_package_defaults,
    )

    # Layer 2: Load .env files hierarchy for app-specific secrets
    if use_env_files:
        try:
            env_config = load_env_config(app_name)

            # Override specific values from .env files
            # These take precedence over package defaults and config files
            # but are lower than environment variables
            if "DATABASE_PATH" in env_config.config:
                config.database.path = Path(env_config.config["DATABASE_PATH"])

            if "CLAUDE_TIMEOUT" in env_config.config:
                config.claude.timeout = int(env_config.config["CLAUDE_TIMEOUT"])

            if "HIVE_LOG_LEVEL" in env_config.config:
                config.logging.level = env_config.config["HIVE_LOG_LEVEL"]

            if "WORKER_TIMEOUT" in env_config.config:
                config.orchestration.worker_timeout = int(env_config.config["WORKER_TIMEOUT"])

            logger.debug(f"Loaded {len(env_config.config)} environment variables for {app_name}")

        except Exception as e:
            logger.warning(f"Failed to load .env files for {app_name}: {e}")

    # Set app-specific metadata
    if app_root:
        config.project_root = app_root
    else:
        # Try to infer app root
        from .paths import get_project_root

        project_root = get_project_root()
        config.project_root = project_root / "apps" / app_name

    logger.info(f"Loaded unified configuration for app: {app_name}")
    logger.debug(
        f"  - Package defaults: {use_package_defaults}"
        f"  - Env files: {use_env_files}"
        f"  - Environment vars: {use_environment}"
    )

    return config


def get_app_specific_config(app_name: str, config_keys: list[str]) -> dict[str, str]:
    """
    Get only specific configuration keys for an app.

    This is a convenience function for apps that only need a few config values.

    Args:
        app_name: Name of the application
        config_keys: List of required configuration keys

    Returns:
        Dictionary with requested configuration values

    Raises:
        ValueError: If any required keys are missing

    Example:
        >>> config = get_app_specific_config(
        ...     "ai-reviewer",
        ...     ["ANTHROPIC_API_KEY", "DATABASE_PATH"]
        ... )
        >>> api_key = config["ANTHROPIC_API_KEY"]
    """
    from .loader import get_required_keys

    return get_required_keys(app_name, config_keys)
