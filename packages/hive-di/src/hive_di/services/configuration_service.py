"""
Configuration Service Implementation

Injectable configuration service that replaces the global configuration singleton.
Supports multiple configuration sources and proper dependency injection.
"""

import os
import json
from pathlib import Path
from typing import Any, Dict, Optional, Union
from dataclasses import dataclass, asdict

from ..interfaces import IConfigurationService, IDisposable


@dataclass
class DatabaseConfig:
    """Database configuration settings"""
    min_connections: int = 2
    max_connections: int = 10
    connection_timeout: float = 30.0
    database_path: Optional[str] = None


@dataclass
class ClaudeConfig:
    """Claude service configuration settings"""
    mock_mode: bool = False
    timeout: float = 30.0
    rate_limit_requests: int = 100
    rate_limit_window: int = 60
    api_key: Optional[str] = None


@dataclass
class EventBusConfig:
    """Event bus configuration settings"""
    max_events_in_memory: int = 1000
    event_retention_days: int = 30
    enable_async: bool = True


@dataclass
class ErrorReportingConfig:
    """Error reporting configuration settings"""
    max_errors_in_memory: int = 500
    error_retention_days: int = 90
    enable_email_alerts: bool = False
    alert_email: Optional[str] = None


@dataclass
class ClimateConfig:
    """Climate service configuration settings"""
    default_adapter: str = "meteostat"
    cache_enabled: bool = True
    cache_ttl: int = 3600
    max_parallel_requests: int = 5


@dataclass
class HiveConfiguration:
    """Complete Hive platform configuration"""
    database: DatabaseConfig
    claude: ClaudeConfig
    event_bus: EventBusConfig
    error_reporting: ErrorReportingConfig
    climate: ClimateConfig


class ConfigurationService(IConfigurationService, IDisposable):
    """
    Injectable configuration service

    Replaces the global configuration singleton with a proper service that can be
    injected and configured independently for different environments.
    """

    def __init__(self,
                 config_source: Optional[Union[str, Path, Dict[str, Any]]] = None,
                 config_path: Optional[Path] = None,
                 use_environment: bool = True):
        """
        Initialize configuration service

        Args:
            config_source: Configuration source (dict, file path, or JSON string)
            config_path: Path to configuration file (deprecated, use config_source)
            use_environment: Whether to override with environment variables
        """
        self._config = self._load_configuration(config_source or config_path, use_environment)
        self._environment_override = use_environment

    def _load_configuration(self,
                           source: Optional[Union[str, Path, Dict[str, Any]]],
                           use_environment: bool) -> HiveConfiguration:
        """Load configuration from various sources"""

        # Start with defaults
        config_dict = self._get_default_config()

        # Load from source if provided
        if source is not None:
            if isinstance(source, dict):
                # Direct dictionary
                config_dict.update(source)
            elif isinstance(source, (str, Path)):
                # File path
                file_config = self._load_from_file(Path(source))
                if file_config:
                    config_dict.update(file_config)
            else:
                raise ValueError(f"Invalid config source type: {type(source)}")

        # Override with environment variables if requested
        if use_environment:
            env_config = self._load_from_environment()
            config_dict.update(env_config)

        return self._dict_to_config(config_dict)

    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration values"""
        return {
            'database': {
                'min_connections': 2,
                'max_connections': 10,
                'connection_timeout': 30.0,
                'database_path': None
            },
            'claude': {
                'mock_mode': False,
                'timeout': 30.0,
                'rate_limit_requests': 100,
                'rate_limit_window': 60,
                'api_key': None
            },
            'event_bus': {
                'max_events_in_memory': 1000,
                'event_retention_days': 30,
                'enable_async': True
            },
            'error_reporting': {
                'max_errors_in_memory': 500,
                'error_retention_days': 90,
                'enable_email_alerts': False,
                'alert_email': None
            },
            'climate': {
                'default_adapter': 'meteostat',
                'cache_enabled': True,
                'cache_ttl': 3600,
                'max_parallel_requests': 5
            }
        }

    def _load_from_file(self, file_path: Path) -> Optional[Dict[str, Any]]:
        """Load configuration from a JSON file"""
        if not file_path.exists():
            return None

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            raise ValueError(f"Failed to load configuration from {file_path}: {e}")

    def _load_from_environment(self) -> Dict[str, Any]:
        """Load configuration overrides from environment variables"""
        env_config = {}

        # Database config
        if os.getenv('HIVE_DB_MIN_CONNECTIONS'):
            env_config.setdefault('database', {})['min_connections'] = int(os.getenv('HIVE_DB_MIN_CONNECTIONS'))
        if os.getenv('HIVE_DB_MAX_CONNECTIONS'):
            env_config.setdefault('database', {})['max_connections'] = int(os.getenv('HIVE_DB_MAX_CONNECTIONS'))
        if os.getenv('HIVE_DB_TIMEOUT'):
            env_config.setdefault('database', {})['connection_timeout'] = float(os.getenv('HIVE_DB_TIMEOUT'))
        if os.getenv('HIVE_DB_PATH'):
            env_config.setdefault('database', {})['database_path'] = os.getenv('HIVE_DB_PATH')

        # Claude config
        if os.getenv('HIVE_CLAUDE_MOCK_MODE'):
            env_config.setdefault('claude', {})['mock_mode'] = os.getenv('HIVE_CLAUDE_MOCK_MODE').lower() == 'true'
        if os.getenv('HIVE_CLAUDE_TIMEOUT'):
            env_config.setdefault('claude', {})['timeout'] = float(os.getenv('HIVE_CLAUDE_TIMEOUT'))
        if os.getenv('HIVE_CLAUDE_API_KEY'):
            env_config.setdefault('claude', {})['api_key'] = os.getenv('HIVE_CLAUDE_API_KEY')

        # Event bus config
        if os.getenv('HIVE_EVENTS_MAX_MEMORY'):
            env_config.setdefault('event_bus', {})['max_events_in_memory'] = int(os.getenv('HIVE_EVENTS_MAX_MEMORY'))
        if os.getenv('HIVE_EVENTS_RETENTION_DAYS'):
            env_config.setdefault('event_bus', {})['event_retention_days'] = int(os.getenv('HIVE_EVENTS_RETENTION_DAYS'))

        return env_config

    def _dict_to_config(self, config_dict: Dict[str, Any]) -> HiveConfiguration:
        """Convert dictionary to typed configuration object"""
        return HiveConfiguration(
            database=DatabaseConfig(**config_dict.get('database', {})),
            claude=ClaudeConfig(**config_dict.get('claude', {})),
            event_bus=EventBusConfig(**config_dict.get('event_bus', {})),
            error_reporting=ErrorReportingConfig(**config_dict.get('error_reporting', {})),
            climate=ClimateConfig(**config_dict.get('climate', {}))
        )

    # IConfigurationService interface implementation

    def get_database_config(self) -> Dict[str, Any]:
        """Get database configuration"""
        return asdict(self._config.database)

    def get_claude_config(self) -> Dict[str, Any]:
        """Get Claude service configuration"""
        return asdict(self._config.claude)

    def get_event_bus_config(self) -> Dict[str, Any]:
        """Get event bus configuration"""
        return asdict(self._config.event_bus)

    def get_error_reporting_config(self) -> Dict[str, Any]:
        """Get error reporting configuration"""
        return asdict(self._config.error_reporting)

    def get_climate_config(self) -> Dict[str, Any]:
        """Get climate service configuration"""
        return asdict(self._config.climate)

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value by dotted key (e.g., 'database.max_connections')"""
        keys = key.split('.')
        value = asdict(self._config)

        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default

    def reload(self) -> None:
        """Reload configuration from original source"""
        # For now, this is a no-op since we don't track the original source
        # Could be enhanced to support live configuration reloading
        pass

    # IDisposable interface implementation

    def dispose(self) -> None:
        """Clean up configuration service resources"""
        # Configuration service doesn't hold any resources that need cleanup
        pass

    # Additional utility methods

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary"""
        return asdict(self._config)

    def get_typed_config(self) -> HiveConfiguration:
        """Get the full typed configuration object"""
        return self._config

    def update(self, updates: Dict[str, Any]) -> None:
        """Update configuration with new values"""
        current_dict = asdict(self._config)
        self._deep_update(current_dict, updates)
        self._config = self._dict_to_config(current_dict)

    def _deep_update(self, base_dict: Dict[str, Any], updates: Dict[str, Any]) -> None:
        """Recursively update nested dictionaries"""
        for key, value in updates.items():
            if key in base_dict and isinstance(base_dict[key], dict) and isinstance(value, dict):
                self._deep_update(base_dict[key], value)
            else:
                base_dict[key] = value