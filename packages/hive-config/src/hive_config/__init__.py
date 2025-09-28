"""
Hive Configuration Management

Secure, hierarchical configuration loading for Hive applications.
Provides centralized access to API keys and app-specific settings.
"""

from .loader import load_config_for_app, get_required_keys, AppConfig, find_project_root
from .models import ConfigSources
from .validation import (
    ValidationError,
    run_comprehensive_validation,
    format_validation_report,
    validate_python_environment,
    validate_project_structure,
    validate_database_connectivity,
    validate_worker_requirements
)

__all__ = [
    # Loader exports
    'load_config_for_app',
    'get_required_keys',
    'AppConfig',
    'find_project_root',
    # Model exports
    'ConfigSources',
    # Validation exports
    'ValidationError',
    'run_comprehensive_validation',
    'format_validation_report',
    'validate_python_environment',
    'validate_project_structure',
    'validate_database_connectivity',
    'validate_worker_requirements',
    # Unified config exports
    'HiveConfig',
    'DatabaseConfig',
    'ClaudeConfig',
    'OrchestrationConfig',
    'WorkerConfig',
    'AIConfig',
    'LoggingConfig',
    'load_config',
    'get_config',
    'reset_config'
]

__version__ = "1.1.0"

from .unified_config import (
    HiveConfig,
    DatabaseConfig,
    ClaudeConfig,
    OrchestrationConfig,
    WorkerConfig,
    AIConfig,
    LoggingConfig,
    load_config,
    get_config,
    reset_config
)
