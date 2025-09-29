from hive_logging import get_logger

logger = get_logger(__name__)

"""
Configuration models and data structures for Hive config management.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any


class ConfigSources(Enum):
    """Sources of configuration values for tracking and debugging"""

    GLOBAL = "global"  # .env.global (Hive system secrets)
    SHARED = "shared"  # .env.shared (shared API keys and config)
    APP = "app"  # apps/{name}/.env (app-specific)
    SYSTEM = "system"  # System environment variables


@dataclass
class AppConfig:
    """
    Secure, hierarchical configuration for Hive apps.

    Tracks configuration values and their sources for security auditing
    and debugging purposes.
    """

    app_name: str
    config: dict[str, Any]
    sources: dict[str, ConfigSources]  # Track where each config came from

    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value with optional default"""
        return self.config.get(key, default)

    def get_source(self, key: str) -> ConfigSources:
        """Get the source of a configuration value"""
        return self.sources.get(key, ConfigSources.SYSTEM)

    def has_key(self, key: str) -> bool:
        """Check if a configuration key exists"""
        return key in self.config

    def get_keys_by_source(self, source: ConfigSources) -> dict[str, Any]:
        """Get all configuration keys from a specific source"""
        return {key: value for key, value in self.config.items() if self.sources.get(key) == source}

    def audit_report(self) -> dict[str, Any]:
        """Generate an audit report of configuration sources"""
        report = {"app_name": self.app_name, "total_keys": len(self.config), "by_source": {}}

        for source in ConfigSources:
            keys = self.get_keys_by_source(source)
            report["by_source"][source.value] = {"count": len(keys), "keys": list(keys.keys())}

        return report
