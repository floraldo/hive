"""Pytest configuration and fixtures for hive-architect."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from hive_architect.api.main import create_app
from hive_architect.config import HiveArchitectConfig


@pytest.fixture
def test_config() -> HiveArchitectConfig:
    """Create test configuration."""
    return HiveArchitectConfig(
        environment="test",
database_path=":memory:",  # In-memory database for tests
cache_enabled=False,  # Disable cache for tests
)


@pytest.fixture
def test_app(test_config: HiveArchitectConfig) -> TestClient:
    """Create test FastAPI client."""
    app = create_app(test_config)
    return TestClient(app)
