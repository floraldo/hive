"""
EcoSystemiser Configuration - Inherit→Extend Pattern

This module extends hive-config with EcoSystemiser-specific configuration.
It properly follows the inherit→extend pattern:
- Inherit: Use hive_config.load_config_for_app for hierarchical loading
- Extend: EcoSystemiser-specific schema and business logic
"""

from typing import Dict, Optional, List
from pathlib import Path

# Inherit from hive-config infrastructure
from hive_config import load_config_for_app, AppConfig
from hive_logging import get_logger

logger = get_logger(__name__)

def get_ecosystemiser_config() -> AppConfig:
    """
    Get EcoSystemiser-specific configuration using proper app hierarchy.

    This follows the inherit→extend pattern:
    - Uses hive_config infrastructure for hierarchical loading
    - Loads from apps/ecosystemiser/.env for app-specific settings
    - Inherits shared API keys from .env.shared
    - Respects system environment overrides

    Returns:
        AppConfig with EcoSystemiser-specific configuration
    """
    return load_config_for_app("ecosystemiser")

def get_ecosystemiser_settings() -> Dict:
    """
    Get EcoSystemiser-specific settings as a dictionary.

    Returns:
        Dictionary of app-specific configuration values
    """
    config = get_ecosystemiser_config()
    return config.config

def get_ecosystemiser_required_keys(required: List[str]) -> Dict[str, str]:
    """
    Get only required configuration keys for EcoSystemiser.

    Args:
        required: List of required configuration keys

    Returns:
        Dictionary with only the requested keys

    Raises:
        ValueError: If any required keys are missing
    """
    from hive_config import get_required_keys
    return get_required_keys("ecosystemiser", required)

# Legacy compatibility functions with deprecation warnings
import warnings

def get_app_config() -> Dict:
    """
    DEPRECATED: Use get_ecosystemiser_settings() instead.

    Returns:
        Complete configuration dictionary for EcoSystemiser
    """
    warnings.warn(
        "get_app_config() is deprecated. Use get_ecosystemiser_settings() instead.",
        DeprecationWarning,
        stacklevel=2
    )
    return get_ecosystemiser_settings()

def get_app_settings() -> Dict:
    """
    DEPRECATED: Use get_ecosystemiser_settings() instead.

    Returns:
        App-specific settings
    """
    warnings.warn(
        "get_app_settings() is deprecated. Use get_ecosystemiser_settings() instead.",
        DeprecationWarning,
        stacklevel=2
    )
    return get_ecosystemiser_settings()

# Legacy compatibility
HIVE_CONFIG_AVAILABLE = True

# Export for backward compatibility and new functions
__all__ = [
    # New inherit→extend pattern functions
    'get_ecosystemiser_config',
    'get_ecosystemiser_settings',
    'get_ecosystemiser_required_keys',
    # Legacy compatibility
    'get_app_config',
    'get_app_settings',
    'HIVE_CONFIG_AVAILABLE'
]