"""
Hive Configuration Management

Secure, hierarchical configuration loading for Hive applications.
Provides centralized access to API keys and app-specific settings.
Includes centralized Python path management for the Hive workspace.
"""

from .loader import load_config_for_app, get_required_keys, AppConfig, find_project_root
from .models import ConfigSources
from .path_manager import (
    setup_hive_paths,
    setup_hive_paths_for_app,
    get_hive_paths,
    get_current_python_path_info,
    validate_hive_imports
)
from .validation import (
    ValidationError,
    run_comprehensive_validation,
    format_validation_report,
    validate_python_environment,
    validate_project_structure,
    validate_database_connectivity,
    validate_import_system,
    validate_worker_requirements
)

__all__ = [
    'load_config_for_app',
    'get_required_keys',
    'AppConfig',
    'ConfigSources',
    'find_project_root',
    'setup_hive_paths',
    'setup_hive_paths_for_app',
    'get_hive_paths',
    'get_current_python_path_info',
    'validate_hive_imports',
    'ValidationError',
    'run_comprehensive_validation',
    'format_validation_report',
    'validate_python_environment',
    'validate_project_structure',
    'validate_database_connectivity',
    'validate_import_system',
    'validate_worker_requirements'
]

__version__ = "1.1.0"from .unified_config import (
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
