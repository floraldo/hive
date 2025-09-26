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
    'validate_hive_imports'
]

__version__ = "1.1.0"