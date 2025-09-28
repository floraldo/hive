"""
Test Helpers - Utility functions for Hive platform testing.

Provides common testing utilities and fixtures for use across
the entire Hive ecosystem.
"""

from pathlib import Path
from typing import Optional
from hive_config.paths import get_project_root




def find_hive_app_root(start_path: Optional[Path] = None) -> Optional[Path]:
    """
    Find the root directory of a Hive app by looking for hive-app.toml.

    Args:
        start_path: Starting directory (defaults to current file's directory)

    Returns:
        Path to app root, or None if not found
    """
    if start_path is None:
        start_path = Path(__file__).resolve()

    current = start_path if start_path.is_dir() else start_path.parent

    # Walk up looking for hive-app.toml
    for parent in [current] + list(current.parents):
        if (parent / "hive-app.toml").exists():
            return parent

    return None


def find_hive_package_root(start_path: Optional[Path] = None) -> Optional[Path]:
    """
    Find the root directory of a Hive package by looking for pyproject.toml.

    Args:
        start_path: Starting directory (defaults to current file's directory)

    Returns:
        Path to package root, or None if not found
    """
    if start_path is None:
        start_path = Path(__file__).resolve()

    current = start_path if start_path.is_dir() else start_path.parent

    # Walk up looking for pyproject.toml (but not the workspace root)
    for parent in [current] + list(current.parents):
        pyproject_path = parent / "pyproject.toml"
        if pyproject_path.exists():
            # Check if this is a package (has src/ directory) not the workspace root
            if (parent / "src").exists() and not (parent / "apps").exists():
                return parent

    return None