"""
Pytest configuration for hive-tests.
"""

import pytest
from pathlib import Path
from hive_config.paths import get_project_root


@pytest.fixture
def project_root():
    """Fixture providing the Hive project root directory."""
    return get_project_root()


@pytest.fixture
def apps_dir(project_root):
    """Fixture providing the apps directory."""
    return project_root / "apps"


@pytest.fixture
def packages_dir(project_root):
    """Fixture providing the packages directory."""
    return project_root / "packages"