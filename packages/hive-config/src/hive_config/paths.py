from hive_logging import get_logger

logger = get_logger(__name__)

"""
Hive Project Path Management

Single source of truth for all filesystem paths in the Hive system.
This module provides a singleton pattern to ensure all components
use consistent, absolute paths derived from the project root.
"""

import functools
import os
from pathlib import Path


def _search_for_root(start_path: Path) -> Path:
    """
    Helper function to search for project root from a starting path.

    Args:
        start_path: Path to start searching from

    Returns:
        Path to project root if found, None otherwise
    """
    current_path = start_path

    # Walk up the directory tree
    while current_path != current_path.parent:
        pyproject_path = current_path / "pyproject.toml"

        if pyproject_path.exists():
            try:
                content = pyproject_path.read_text(encoding="utf-8")
                # Look for the workspace root identifier
                if 'name = "hive-workspace"' in content:
                    return current_path
            except Exception as e:
                # Continue searching if we can't read the file
                pass

        current_path = current_path.parent

    return None


@functools.lru_cache(maxsize=1)
def get_project_root() -> Path:
    """
    Finds the absolute path to the project root by looking for the
    main `pyproject.toml` file that defines the Poetry workspace.

    This function is cached, so it only runs the search once per process.

    Returns:
        Path: Absolute path to the project root directory

    Raises:
        RuntimeError: If the project root cannot be found
    """
    # First, check environment variable override
    if env_root := os.environ.get("HIVE_PROJECT_ROOT"):
        env_path = Path(env_root)
        if env_path.exists() and (env_path / "pyproject.toml").exists():
            return env_path

    # Second, try from current working directory (for scripts running in project)
    current_path = Path.cwd()
    if root := _search_for_root(current_path):
        return root

    # Third, fallback to searching from this file's location (for installed packages)
    current_path = Path(__file__).resolve()
    if root := _search_for_root(current_path):
        return root

    # Fourth, check common development locations for Windows
    common_dev_paths = [
        Path("C:/git/hive")
        Path("C:/src/hive"),
        Path("C:/code/hive")
        Path("C:/dev/hive"),
        Path.home() / "git" / "hive",
        Path.home() / "src" / "hive",
        Path.home() / "code" / "hive",
        Path.home() / "dev" / "hive",
    ]

    for dev_path in common_dev_paths:
        if dev_path.exists() and (dev_path / "pyproject.toml").exists():
            try:
                content = (dev_path / "pyproject.toml").read_text(encoding="utf-8")
                if 'name = "hive-workspace"' in content:
                    # Cache this for future use
                    os.environ["HIVE_PROJECT_ROOT"] = str(dev_path)
                    return dev_path
            except Exception as e:
                continue

    # If we can't find the workspace root, raise an error with helpful information
    raise RuntimeError(
        "Could not find the Hive project root. "
        "Make sure this code is running within the Hive project directory, "
        "or set the HIVE_PROJECT_ROOT environment variable to the project root path. "
        f"Searched from: {Path.cwd()}, {Path(__file__).resolve().parent}"
    )


# Define the authoritative project root
PROJECT_ROOT = get_project_root()

# Define key paths as constants derived from the root
APPS_DIR = PROJECT_ROOT / "apps"
PACKAGES_DIR = PROJECT_ROOT / "packages"
HIVE_DIR = PROJECT_ROOT / "hive"
DB_PATH = HIVE_DIR / "db" / "hive-internal.db"
WORKTREES_DIR = PROJECT_ROOT / ".worktrees"
LOGS_DIR = HIVE_DIR / "logs"

# Additional common paths
SCRIPTS_DIR = PROJECT_ROOT / "scripts"


def ensure_directory(path: Path) -> Path:
    """
    Ensure a directory exists, creating it if necessary.

    Args:
        path: The directory path to ensure exists

    Returns:
        Path: The same path, guaranteed to exist
    """
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_worker_workspace_dir(worker_id: str, task_id: str = None) -> Path:
    """
    Get the workspace directory for a specific worker and task.

    Args:
        worker_id: The worker identifier (e.g., 'backend', 'frontend')
        task_id: The task identifier (optional)

    Returns:
        Path: The workspace directory path
    """
    base_path = WORKTREES_DIR / worker_id

    if task_id:
        return base_path / task_id
    else:
        return base_path


def get_task_log_dir(task_id: str) -> Path:
    """
    Get the log directory for a specific task.

    Args:
        task_id: The task identifier

    Returns:
        Path: The task log directory path
    """
    return LOGS_DIR / task_id
