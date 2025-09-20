"""
EcoSystemiser configuration integration with Hive config service.

This module provides EcoSystemiser with secure access to configuration
through Hive's centralized configuration management.
"""

from typing import Dict, Optional, List
import logging

try:
    from hive_config.loader import load_config_for_app, get_required_keys
    HIVE_CONFIG_AVAILABLE = True
except ImportError:
    HIVE_CONFIG_AVAILABLE = False
    import os

logger = logging.getLogger(__name__)


def get_ecosystemiser_config():
    """
    Get EcoSystemiser configuration using secure config service.

    Returns:
        Complete configuration dictionary for EcoSystemiser
    """
    if HIVE_CONFIG_AVAILABLE:
        try:
            config = load_config_for_app("ecosystemiser")
            logger.info(f"Loaded EcoSystemiser config from Hive: {len(config.config)} keys")
            return config.config
        except Exception as e:
            logger.warning(f"Failed to load Hive config, falling back to environment: {e}")

    # Fallback to direct environment access
    logger.info("Using fallback environment configuration")
    return dict(os.environ)


def get_required_api_keys() -> Dict[str, str]:
    """
    Get required API keys with explicit declaration for security.

    This is the secure way to request only the API keys EcoSystemiser needs.

    Returns:
        Dictionary of required API keys

    Raises:
        ValueError: If required keys are missing
    """
    # Define what EcoSystemiser explicitly needs
    required_keys = [
        # Core AI APIs for processing
        'OPENAI_API_KEY',
        'ANTHROPIC_API_KEY',

        # Weather data APIs
        'NASA_POWER_API_KEY',
        'METEOSTAT_API_KEY',
        'ERA5_API_KEY',
        'PVGIS_API_KEY',
        'OPENWEATHER_API_KEY',
    ]

    if HIVE_CONFIG_AVAILABLE:
        try:
            return get_required_keys("ecosystemiser", required_keys)
        except Exception as e:
            logger.error(f"Failed to get required keys from Hive: {e}")
            raise

    # Fallback to environment
    result = {}
    missing = []

    for key in required_keys:
        value = os.getenv(key)
        if value:
            result[key] = value
        else:
            missing.append(key)

    if missing:
        raise ValueError(f"Missing required API keys: {missing}")

    return result


def get_app_settings() -> Dict[str, str]:
    """
    Get app-specific settings (non-sensitive configuration).

    Returns:
        Dictionary of app-specific settings
    """
    if HIVE_CONFIG_AVAILABLE:
        config = load_config_for_app("ecosystemiser").config
    else:
        config = dict(os.environ)

    return {
        'ECOSYSTEMISER_PORT': config.get('ECOSYSTEMISER_PORT', '8001'),
        'ECOSYSTEMISER_HOST': config.get('ECOSYSTEMISER_HOST', '0.0.0.0'),
        'ECOSYSTEMISER_CACHE_DIR': config.get('ECOSYSTEMISER_CACHE_DIR', './cache'),
        'ECOSYSTEMISER_DATA_DIR': config.get('ECOSYSTEMISER_DATA_DIR', './data'),
        'ECOSYSTEMISER_LOG_LEVEL': config.get('ECOSYSTEMISER_LOG_LEVEL', 'INFO'),
        'ECOSYSTEMISER_WORKERS': config.get('ECOSYSTEMISER_WORKERS', '4'),
        'ECOSYSTEMISER_MAX_BATCH_SIZE': config.get('ECOSYSTEMISER_MAX_BATCH_SIZE', '100'),

        # Rate limiting settings
        'RATE_LIMIT_NASA_POWER': config.get('RATE_LIMIT_NASA_POWER', '30'),
        'RATE_LIMIT_METEOSTAT': config.get('RATE_LIMIT_METEOSTAT', '60'),
        'RATE_LIMIT_ERA5': config.get('RATE_LIMIT_ERA5', '10'),
        'RATE_LIMIT_PVGIS': config.get('RATE_LIMIT_PVGIS', '20'),

        # Feature flags
        'ENABLE_CACHING': config.get('ENABLE_CACHING', 'true'),
        'ENABLE_RATE_LIMITING': config.get('ENABLE_RATE_LIMITING', 'true'),
        'ENABLE_METRICS': config.get('ENABLE_METRICS', 'true'),
        'DEBUG': config.get('DEBUG', 'false'),
    }


def is_hive_environment() -> bool:
    """
    Check if we're running within the Hive environment.

    Returns:
        True if running in Hive with config service, False if standalone
    """
    return HIVE_CONFIG_AVAILABLE


# Export main functions
__all__ = [
    'get_ecosystemiser_config',
    'get_required_api_keys',
    'get_app_settings',
    'is_hive_environment',
    'HIVE_CONFIG_AVAILABLE'
]