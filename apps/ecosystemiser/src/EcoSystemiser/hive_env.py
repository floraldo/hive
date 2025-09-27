"""
EcoSystemiser configuration integration with Hive config service.

This module provides EcoSystemiser with secure access to configuration
through Hive's centralized configuration management.
"""

from typing import Dict, Optional, List
from EcoSystemiser.hive_logging_adapter import get_logger
import os

try:
    from hive_config.loader import load_config_for_app, get_required_keys
    HIVE_CONFIG_AVAILABLE = True
except ImportError:
    HIVE_CONFIG_AVAILABLE = False

logger = get_logger(__name__)

def get_app_config():
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
        Dictionary of app-specific settings with simplified names
    """
    if HIVE_CONFIG_AVAILABLE:
        config = load_config_for_app("ecosystemiser").config
    else:
        config = dict(os.environ)

    return {
        # Server settings with simplified names
        'PORT': config.get('PORT', '8001'),
        'HOST': config.get('HOST', '0.0.0.0'),
        'WORKERS': config.get('WORKERS', '4'),
        'LOG_LEVEL': config.get('LOG_LEVEL', 'INFO'),

        # Storage paths
        'CACHE_DIR': config.get('CACHE_DIR', './cache'),
        'DATA_DIR': config.get('DATA_DIR', './data'),
        'RESULTS_DIR': config.get('RESULTS_DIR', './ecosystemiser_results'),

        # Processing settings
        'MAX_BATCH_SIZE': config.get('MAX_BATCH_SIZE', '100'),
        'ENABLE_CACHING': config.get('ENABLE_CACHING', 'true'),
        'ENABLE_RATE_LIMITING': config.get('ENABLE_RATE_LIMITING', 'true'),
        'ENABLE_METRICS': config.get('ENABLE_METRICS', 'true'),
        'DEBUG': config.get('DEBUG', 'false'),

        # Rate limiting settings
        'RATE_LIMIT_NASA_POWER': config.get('RATE_LIMIT_NASA_POWER', '30'),
        'RATE_LIMIT_METEOSTAT': config.get('RATE_LIMIT_METEOSTAT', '60'),
        'RATE_LIMIT_ERA5': config.get('RATE_LIMIT_ERA5', '10'),
        'RATE_LIMIT_PVGIS': config.get('RATE_LIMIT_PVGIS', '20'),

        # Climate adapter settings
        'NASA_POWER_ENABLED': config.get('NASA_POWER_ENABLED', 'true'),
        'METEOSTAT_ENABLED': config.get('METEOSTAT_ENABLED', 'true'),
        'ERA5_ENABLED': config.get('ERA5_ENABLED', 'true'),
        'PVGIS_ENABLED': config.get('PVGIS_ENABLED', 'true'),
        'EPW_ENABLED': config.get('EPW_ENABLED', 'true'),
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