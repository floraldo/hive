"""Pytest configuration and fixtures for hive-ui."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from hive_ui.api.main import create_app
from hive_ui.config import HiveUiConfig


@pytest.fixture
def test_config() -> HiveUiConfig:
    """Create test configuration."""
    return HiveUiConfig(
        environment="test",
cache_enabled=False,  # Disable cache for tests
)


@pytest.fixture
def test_app(test_config: HiveUiConfig) -> TestClient:
    """Create test FastAPI client."""
    app = create_app(test_config)
    return TestClient(app)
