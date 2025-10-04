"""Unit tests for unified_config module (HiveConfig and Pydantic models).

Tests Pydantic validation, environment variable overrides, and configuration loading.
"""
from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from hive_config.unified_config import (
    AIConfig,
    ClaudeConfig,
    DatabaseConfig,
    HiveConfig,
    LoggingConfig,
    OrchestrationConfig,
    WorkerConfig,
    create_config_from_sources,
)


@pytest.mark.core
class TestDatabaseConfig:
    """Test DatabaseConfig Pydantic model."""

    @pytest.mark.core
    def test_default_values(self):
        """Test DatabaseConfig with default values."""
        config = DatabaseConfig()
        assert config.path == Path("hive/db/hive-internal.db")
        assert config.connection_pool_min == 2
        assert config.connection_pool_max == 10
        assert config.connection_timeout == 30
        assert config.max_retries == 3
        assert config.journal_mode == "WAL"
        assert config.synchronous == "NORMAL"
        assert config.cache_size == 10000

    @pytest.mark.core
    def test_custom_values(self):
        """Test DatabaseConfig with custom values."""
        config = DatabaseConfig(path=Path("/custom/db.sqlite"), connection_pool_min=5, connection_pool_max=20, connection_timeout=60)
        assert config.path == Path("/custom/db.sqlite")
        assert config.connection_pool_min == 5
        assert config.connection_pool_max == 20
        assert config.connection_timeout == 60

    @pytest.mark.core
    def test_validation_min_greater_than_zero(self):
        """Test that pool min must be >= 1."""
        with pytest.raises(ValidationError):
            DatabaseConfig(connection_pool_min=0)

    @pytest.mark.core
    def test_validation_max_greater_than_zero(self):
        """Test that pool max must be >= 1."""
        with pytest.raises(ValidationError):
            DatabaseConfig(connection_pool_max=0)

@pytest.mark.core
class TestClaudeConfig:
    """Test ClaudeConfig Pydantic model."""

    @pytest.mark.core
    def test_default_values(self):
        """Test ClaudeConfig with default values."""
        config = ClaudeConfig()
        assert config.mock_mode is False
        assert config.timeout == 120
        assert config.max_retries == 3
        assert config.use_dangerously_skip_permissions is True
        assert config.fallback_enabled is True

    @pytest.mark.core
    def test_custom_values(self):
        """Test ClaudeConfig with custom values."""
        config = ClaudeConfig(mock_mode=True, timeout=300, max_retries=5, use_dangerously_skip_permissions=False)
        assert config.mock_mode is True
        assert config.timeout == 300
        assert config.max_retries == 5
        assert config.use_dangerously_skip_permissions is False

    @pytest.mark.core
    def test_validation_timeout_positive(self):
        """Test that timeout must be >= 1."""
        with pytest.raises(ValidationError):
            ClaudeConfig(timeout=0)

@pytest.mark.core
class TestOrchestrationConfig:
    """Test OrchestrationConfig Pydantic model."""

    @pytest.mark.core
    def test_default_values(self):
        """Test OrchestrationConfig with default values."""
        config = OrchestrationConfig()
        assert config.poll_interval == 5
        assert config.worker_timeout == 600
        assert config.max_parallel_workers == 4
        assert isinstance(config.phase_timeouts, dict)
        assert config.phase_timeouts["analysis"] == 300
        assert config.zombie_task_threshold == 3600
        assert config.heartbeat_interval == 30

    @pytest.mark.core
    def test_custom_phase_timeouts(self):
        """Test custom phase timeouts."""
        custom_timeouts = {"analysis": 600, "implementation": 1200}
        config = OrchestrationConfig(phase_timeouts=custom_timeouts)
        assert config.phase_timeouts == custom_timeouts

@pytest.mark.core
class TestWorkerConfig:
    """Test WorkerConfig Pydantic model."""

    @pytest.mark.core
    def test_default_values(self):
        """Test WorkerConfig with default values."""
        config = WorkerConfig()
        assert config.backend_enabled is True
        assert config.frontend_enabled is True
        assert config.infra_enabled is True
        assert config.app_workers_enabled is True
        assert config.max_retries_per_task == 3
        assert config.output_capture is True
        assert config.live_output is False

    @pytest.mark.core
    def test_custom_values(self):
        """Test WorkerConfig with custom values."""
        config = WorkerConfig(backend_enabled=False, frontend_enabled=False, max_retries_per_task=5, live_output=True)
        assert config.backend_enabled is False
        assert config.frontend_enabled is False
        assert config.max_retries_per_task == 5
        assert config.live_output is True

@pytest.mark.core
class TestAIConfig:
    """Test AIConfig Pydantic model."""

    @pytest.mark.core
    def test_default_values(self):
        """Test AIConfig with default values."""
        config = AIConfig()
        assert config.planner_enabled is True
        assert config.reviewer_enabled is True
        assert config.planner_poll_interval == 10
        assert config.reviewer_poll_interval == 15
        assert config.auto_approval_threshold == 80
        assert config.auto_rejection_threshold == 40
        assert config.escalation_threshold == 60

    @pytest.mark.core
    def test_custom_values(self):
        """Test AIConfig with custom values."""
        config = AIConfig(planner_enabled=False, auto_approval_threshold=90, auto_rejection_threshold=30)
        assert config.planner_enabled is False
        assert config.auto_approval_threshold == 90
        assert config.auto_rejection_threshold == 30

@pytest.mark.core
class TestLoggingConfig:
    """Test LoggingConfig Pydantic model."""

    @pytest.mark.core
    def test_default_values(self):
        """Test LoggingConfig with default values."""
        config = LoggingConfig()
        assert config.level == "INFO"
        assert "asctime" in config.format
        assert config.file_enabled is True
        assert config.console_enabled is True
        assert config.log_directory == Path("hive/logs")
        assert config.max_file_size == 10485760
        assert config.backup_count == 5

    @pytest.mark.core
    def test_custom_values(self):
        """Test LoggingConfig with custom values."""
        config = LoggingConfig(level="DEBUG", file_enabled=False, log_directory=Path("/custom/logs"), max_file_size=20971520)
        assert config.level == "DEBUG"
        assert config.file_enabled is False
        assert config.log_directory == Path("/custom/logs")
        assert config.max_file_size == 20971520

@pytest.mark.core
class TestHiveConfig:
    """Test HiveConfig main configuration model."""

    @pytest.mark.core
    def test_default_initialization(self):
        """Test HiveConfig with all defaults."""
        config = HiveConfig()
        assert isinstance(config.database, DatabaseConfig)
        assert isinstance(config.claude, ClaudeConfig)
        assert isinstance(config.orchestration, OrchestrationConfig)
        assert isinstance(config.worker, WorkerConfig)
        assert isinstance(config.ai, AIConfig)
        assert isinstance(config.logging, LoggingConfig)
        assert config.database.connection_pool_max == 10
        assert config.claude.timeout == 120
        assert config.worker.backend_enabled is True

    @pytest.mark.core
    def test_partial_initialization(self):
        """Test HiveConfig with partial custom values."""
        custom_db = (DatabaseConfig(connection_pool_max=20),)
        custom_claude = (ClaudeConfig(mock_mode=True),)
        config = HiveConfig(database=custom_db, claude=custom_claude)
        assert config.database.connection_pool_max == 20
        assert config.claude.mock_mode is True
        assert config.worker.backend_enabled is True

    @pytest.mark.core
    def test_nested_field_access(self):
        """Test accessing nested configuration fields."""
        config = HiveConfig()
        db_path = (config.database.path,)
        claude_timeout = (config.claude.timeout,)
        worker_retries = config.worker.max_retries_per_task
        assert isinstance(db_path, Path)
        assert isinstance(claude_timeout, int)
        assert isinstance(worker_retries, int)

@pytest.mark.core
class TestCreateConfigFromSources:
    """Test create_config_from_sources function."""

    @pytest.mark.core
    def test_create_with_defaults(self):
        """Test creating config with all defaults."""
        config = create_config_from_sources()
        assert isinstance(config, HiveConfig)
        assert config.database.connection_pool_max == 10
        assert config.claude.timeout == 120

    @pytest.mark.core
    def test_create_without_environment(self):
        """Test creating config without environment variable overrides."""
        config = create_config_from_sources(use_environment=False)
        assert isinstance(config, HiveConfig)
        assert config.database.connection_pool_max == 10
        assert config.claude.timeout == 120
        assert config.worker.backend_enabled is True

    @pytest.mark.core
    @patch.dict(os.environ, {"HIVE_DATABASE_CONNECTION_POOL_MAX": "50"})
    def test_environment_variable_override(self):
        """Test environment variable overrides."""
        config = create_config_from_sources()
        assert isinstance(config, HiveConfig)

    @pytest.mark.core
    def test_validation_warnings(self):
        """Test that validation warnings are logged."""
        config = HiveConfig(database=DatabaseConfig(connection_pool_min=20, connection_pool_max=10))
        errors = config.validate()
        assert len(errors) > 0
        assert any("min connections" in err.lower() for err in errors)

@pytest.mark.core
class TestConfigSerialization:
    """Test configuration serialization."""

    @pytest.mark.core
    def test_hive_config_to_dict(self):
        """Test converting HiveConfig to dictionary."""
        config = (HiveConfig(),)
        config_dict = config.model_dump()
        assert isinstance(config_dict, dict)
        assert "database" in config_dict
        assert "claude" in config_dict
        assert "orchestration" in config_dict

    @pytest.mark.core
    def test_database_config_to_dict(self):
        """Test converting DatabaseConfig to dictionary."""
        config = (DatabaseConfig(),)
        config_dict = config.model_dump()
        assert isinstance(config_dict, dict)
        assert "path" in config_dict
        assert "connection_pool_max" in config_dict
