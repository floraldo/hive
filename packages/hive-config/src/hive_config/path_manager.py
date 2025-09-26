"""
Centralized Python path management for Hive workspace.

This module provides a single source of truth for Python path configuration
across all Hive applications, eliminating the need for repeated sys.path.insert()
calls throughout the codebase.

Usage:
    from hive_config.path_manager import setup_hive_paths
    setup_hive_paths()  # Call once at module start
"""

import sys
import logging
from pathlib import Path
from typing import List, Optional

from .loader import find_project_root

logger = logging.getLogger(__name__)


def get_hive_paths() -> List[Path]:
    """
    Get all standard Hive Python paths that should be available.

    Returns:
        List of Path objects for all Hive packages and apps
    """
    try:
        root = find_project_root()
    except RuntimeError:
        # Fallback for standalone execution
        root = Path(__file__).parent.parent.parent.parent.parent
        logger.warning(f"Could not find project root, using fallback: {root}")

    paths = [
        # Core packages
        root / "packages" / "hive-config" / "src",
        root / "packages" / "hive-core-db" / "src",
        root / "packages" / "hive-utils" / "src",
        root / "packages" / "hive-logging" / "src",
        root / "packages" / "hive-db-utils" / "src",
        root / "packages" / "hive-deployment" / "src",

        # Applications
        root / "apps" / "hive-orchestrator" / "src",
        root / "apps" / "ai-reviewer" / "src",
        root / "apps" / "ecosystemiser" / "src",
    ]

    # Only return paths that actually exist
    existing_paths = [p for p in paths if p.exists()]

    logger.debug(f"Found {len(existing_paths)} valid Hive paths from {len(paths)} candidates")
    return existing_paths


def setup_hive_paths() -> None:
    """
    Configure Python path for Hive workspace components.

    This function should be called once at the start of any Hive application
    to ensure all necessary packages and apps are available for import.

    Features:
    - Automatically detects project root
    - Adds all existing Hive packages to sys.path
    - Avoids duplicate path entries
    - Provides debug logging for troubleshooting
    """
    paths = get_hive_paths()
    added_count = 0

    for path in paths:
        path_str = str(path)
        if path_str not in sys.path:
            sys.path.insert(0, path_str)
            added_count += 1
            logger.debug(f"Added to Python path: {path_str}")
        else:
            logger.debug(f"Path already in sys.path: {path_str}")

    logger.info(f"Hive paths configured: {added_count} new paths added, {len(paths)} total available")


def setup_hive_paths_for_app(app_name: str, additional_paths: Optional[List[str]] = None) -> None:
    """
    Configure Python paths for a specific Hive application.

    This is a specialized version of setup_hive_paths() for applications
    that need additional app-specific paths beyond the standard ones.

    Args:
        app_name: Name of the application (for logging)
        additional_paths: Additional relative paths from project root to include
    """
    setup_hive_paths()

    if additional_paths:
        try:
            root = find_project_root()
            added_count = 0

            for rel_path in additional_paths:
                full_path = root / rel_path
                if full_path.exists():
                    path_str = str(full_path)
                    if path_str not in sys.path:
                        sys.path.insert(0, path_str)
                        added_count += 1
                        logger.debug(f"Added app-specific path for {app_name}: {path_str}")
                else:
                    logger.warning(f"App-specific path does not exist for {app_name}: {full_path}")

            if added_count > 0:
                logger.info(f"Added {added_count} app-specific paths for {app_name}")

        except RuntimeError as e:
            logger.error(f"Could not add app-specific paths for {app_name}: {e}")


def get_current_python_path_info() -> dict:
    """
    Get diagnostic information about current Python path configuration.

    Returns:
        Dictionary with path information for debugging
    """
    try:
        root = find_project_root()
        hive_paths = get_hive_paths()

        return {
            "project_root": str(root),
            "hive_paths_available": len(hive_paths),
            "hive_paths_in_syspath": sum(1 for p in hive_paths if str(p) in sys.path),
            "total_syspath_entries": len(sys.path),
            "first_10_syspath": sys.path[:10]
        }
    except Exception as e:
        return {"error": str(e)}


def validate_hive_imports() -> dict:
    """
    Validate that core Hive packages can be imported after path setup.

    Returns:
        Dictionary with import test results
    """
    test_imports = [
        "hive_config",
        "hive_core_db",
        "hive_utils",
        "hive_logging"
    ]

    results = {}
    for module_name in test_imports:
        try:
            __import__(module_name)
            results[module_name] = "SUCCESS"
        except ImportError as e:
            results[module_name] = f"FAILED: {e}"

    return results