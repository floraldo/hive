from pydantic import BaseModel

from hive_logging import get_logger

logger = get_logger(__name__)


class BaseConfig(BaseModel):
    """Base configuration class for all Hive configurations."""

    class Config:
        """Pydantic configuration."""

        extra = "forbid"
        validate_assignment = True
        use_enum_values = True


"""
Hive Configuration Management

Secure, hierarchical configuration loading for Hive applications.
Provides centralized access to API keys and app-specific settings.
"""

from .loader import AppConfig, find_project_root, get_required_keys, load_config_for_app
from .models import ConfigSources
from .validation import (
    ValidationError,
    format_validation_report,
    run_comprehensive_validation,
    validate_database_connectivity,
    validate_project_structure,
    validate_python_environment,
    validate_worker_requirements,
)

__all__ = [
    # Base exports
    "BaseConfig",
    # Loader exports
    "load_config_for_app",
    "get_required_keys",
    "AppConfig",
    "find_project_root",
    # Model exports
    "ConfigSources",
    # Validation exports
    "ValidationError",
    "run_comprehensive_validation",
    "format_validation_report",
    "validate_python_environment",
    "validate_project_structure",
    "validate_database_connectivity",
    "validate_worker_requirements",
    # Unified config exports
    "HiveConfig",
    "DatabaseConfig",
    "ClaudeConfig",
    "OrchestrationConfig",
    "WorkerConfig",
    "AIConfig",
    "LoggingConfig",
    "load_config",
    "get_config",
    "reset_config",
    # Secure config exports
    "SecureConfigLoader",
    "encrypt_production_config",
    "generate_master_key",
    # Async config exports
    "AsyncConfigLoader",
    "get_async_config_loader",
    "load_app_config_async",
]

__version__ = "1.1.0"

from .async_config import AsyncConfigLoader, load_app_config_async
from .async_config import create_async_config_loader as get_async_config_loader
from .secure_config import SecureConfigLoader, encrypt_production_config, generate_master_key
from .unified_config import (
    AIConfig,
    ClaudeConfig,
    DatabaseConfig,
    HiveConfig,
    LoggingConfig,
    OrchestrationConfig,
    WorkerConfig,
    get_config,
    load_config,
    reset_config,
)
