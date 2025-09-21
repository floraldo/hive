"""
Hive Utilities Package

Core utilities for path management and system coordination.
"""

from .paths import (
    get_project_root,
    PROJECT_ROOT,
    APPS_DIR,
    PACKAGES_DIR,
    HIVE_DIR,
    DB_PATH,
    WORKTREES_DIR,
    LOGS_DIR,
)

__all__ = [
    "get_project_root",
    "PROJECT_ROOT",
    "APPS_DIR",
    "PACKAGES_DIR",
    "HIVE_DIR",
    "DB_PATH",
    "WORKTREES_DIR",
    "LOGS_DIR",
]