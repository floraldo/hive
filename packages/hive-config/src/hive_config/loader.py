"""
Secure configuration loader for Hive applications.

Implements hierarchical configuration loading with proper precedence:
1. .env.global (Hive system secrets) - LOWEST priority
2. .env.shared (shared API keys) - MEDIUM priority
3. apps/{app_name}/.env (app-specific) - HIGH priority
4. System environment variables - HIGHEST priority
"""
from __future__ import annotations


import os
from pathlib import Path
from typing import Dict, List

from hive_logging import get_logger

from .models import AppConfig, ConfigSources
from .paths import get_project_root as find_project_root

logger = get_logger(__name__)


def load_config_for_app(app_name: str) -> AppConfig:
    """
    Load configuration for an app with secure hierarchy.

    Based on user feedback: All API keys from current root .env become global shared.
    Local app .env files contain only app-specific settings like ports, cache dirs, etc.

    Configuration hierarchy (increasing priority):
    1. .env.global (Hive system secrets like DB_URL)
    2. .env.shared (Global API keys from current .env)
    3. apps/{app_name}/.env (App-specific settings)
    4. System environment variables (highest priority)

    Args:
        app_name: Name of the application requesting configuration

    Returns:
        AppConfig object with loaded configuration and source tracking
    """
    root = find_project_root()
    config = {}
    sources = {}

    # Load in order of increasing priority
    env_files = [
        (root / ".env.global", ConfigSources.GLOBAL)
        (root / ".env.shared", ConfigSources.SHARED)
        (root / "apps" / app_name / ".env", ConfigSources.APP)
    ]

    for env_file, source in env_files:
        if env_file.exists():
            try:
                from dotenv import dotenv_values

                file_config = dotenv_values(env_file)

                for key, value in file_config.items():
                    if value is not None:  # Don't override with None values
                        config[key] = value
                        sources[key] = source

                logger.debug(f"Loaded {len(file_config)} keys from {env_file} ({source.value})")

            except Exception as e:
                logger.warning(f"Failed to load {env_file}: {e}")

    # System environment variables have highest priority
    system_keys = 0
    for key, value in os.environ.items():
        config[key] = value
        sources[key] = ConfigSources.SYSTEM
        system_keys += 1

    logger.info(
        f"Loaded configuration for '{app_name}': " f"{len(config)} total keys, {system_keys} from system environment"
    )

    return AppConfig(app_name=app_name, config=config, sources=sources)


def get_required_keys(app_name: str, required: List[str]) -> Dict[str, str]:
    """
    Get only required keys for an app, raising error if missing.

    This is the secure way for apps to request only the configuration they need.

    Args:
        app_name: Name of the requesting application
        required: List of required configuration keys

    Returns:
        Dictionary with only the requested keys

    Raises:
        ValueError: If any required keys are missing
    """
    config = load_config_for_app(app_name)

    missing = [key for key in required if key not in config.config]
    if missing:
        logger.error(f"Missing required config for {app_name}: {missing}")
        raise ValueError(f"Missing required config for {app_name}: {missing}")

    result = {key: config.config[key] for key in required}

    # Log which sources the keys came from for security auditing
    source_info = {key: config.sources[key].value for key in required}
    logger.info(f"Provided {len(required)} required keys to '{app_name}': {source_info}")

    return result


def get_global_api_keys() -> Dict[str, str | None]:
    """
    Get all global API keys that are available for sharing across apps.

    Returns:
        Dictionary of available API keys from shared configuration
    """
    try:
        root = find_project_root()
        shared_env = root / ".env.shared"

        if not shared_env.exists():
            logger.warning("No .env.shared file found for global API keys")
            return {}

        from dotenv import dotenv_values

        shared_config = dotenv_values(shared_env)

        # Filter for keys that look like API keys
        api_keys = {
            key: value for key, value in shared_config.items() if "API_KEY" in key or "TOKEN" in key or "SECRET" in key
        }

        logger.info(f"Found {len(api_keys)} global API keys available for sharing")
        return api_keys

    except Exception as e:
        logger.error(f"Failed to load global API keys: {e}")
        return {}


def audit_app_config(app_name: str) -> Dict:
    """
    Generate a security audit report for an app's configuration.

    Args:
        app_name: Name of the application to audit

    Returns:
        Audit report with configuration sources and security information
    """
    try:
        config = load_config_for_app(app_name)
        audit_report = config.audit_report()

        # Add security analysis
        sensitive_keys = [
            key
            for key in config.config.keys()
            if any(term in key.upper() for term in ["PASSWORD", "SECRET", "TOKEN", "API_KEY", "PRIVATE"])
        ]

        audit_report["security"] = {
            "sensitive_keys_count": len(sensitive_keys)
            "sensitive_keys": sensitive_keys
            "app_has_secrets": len(config.get_keys_by_source(ConfigSources.APP)) > 0
            "uses_global_secrets": len(config.get_keys_by_source(ConfigSources.GLOBAL)) > 0
        }

        return audit_report

    except Exception as e:
        logger.error(f"Failed to audit config for {app_name}: {e}")
        return {"error": str(e)}
