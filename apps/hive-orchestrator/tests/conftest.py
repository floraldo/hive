"""
Pytest configuration and fixtures for hive-orchestrator tests.

Provides shared fixtures for configuration, database, and services
following the dependency injection pattern.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from hive_config import (
    ClaudeConfig,
    DatabaseConfig,
    HiveConfig,
    LoggingConfig,
    OrchestrationConfig,
    WorkerConfig,
    create_config_from_sources,
)


@pytest.fixture
def hive_config() -> HiveConfig:
    """
    Production-like configuration for integration tests.

    Uses actual configuration sources (files, environment variables)
    but suitable for testing environment.
    """
    return create_config_from_sources()


@pytest.fixture
def mock_config() -> HiveConfig:
    """
    Isolated configuration for unit tests.

    Uses in-memory database and mock mode for external services.
    Each test gets independent configuration instance.
    """
    return HiveConfig(
        database=DatabaseConfig(
            path=Path(":memory:"),
            connection_pool_min=1,
            connection_pool_max=2,
            connection_timeout=5,
        ),
        claude=ClaudeConfig(
            mock_mode=True,
            timeout=1,
            max_retries=1,
        ),
        orchestration=OrchestrationConfig(
            poll_interval=1,
            worker_timeout=30,
            max_parallel_workers=2,
        ),
        worker=WorkerConfig(
            spawn_timeout=10,
            status_refresh_seconds=1,
        ),
        logging=LoggingConfig(
            level="DEBUG",
            format="json",
        ),
    )


@pytest.fixture
def test_db_config() -> DatabaseConfig:
    """
    Test database configuration.

    Provides in-memory database for isolated testing.
    """
    return DatabaseConfig(
        path=Path(":memory:"),
        connection_pool_min=1,
        connection_pool_max=2,
    )


@pytest.fixture
def custom_config():
    """
    Config factory for test-specific configuration needs.

    Returns a function that creates HiveConfig with custom overrides.

    Usage:
        def test_something(custom_config):
            config = custom_config(database__path=Path("/tmp/test.db"))
            service = MyService(config=config)
    """

    def _create_config(**overrides) -> HiveConfig:
        # Start with test-friendly defaults
        config = HiveConfig(
            database=DatabaseConfig(path=Path(":memory:")),
            claude=ClaudeConfig(mock_mode=True),
        )

        # Apply overrides
        for key, value in overrides.items():
            if "__" in key:
                # Handle nested attributes (e.g., database__path)
                section, attr = key.split("__", 1)
                section_obj = getattr(config, section)
                setattr(section_obj, attr, value)
            else:
                # Handle top-level attributes
                setattr(config, key, value)

        return config

    return _create_config


@pytest.fixture(autouse=True)
def reset_global_state():
    """
    Reset global state before each test.

    This fixture runs automatically before each test to ensure
    clean state. Useful during migration from global config to DI.

    Note: Once migration is complete, this fixture can be removed.
    """
    # Future: Reset any global state here if needed
    yield
    # Future: Cleanup any global state here if needed
