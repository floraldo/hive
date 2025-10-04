"""Smoke tests for the hive-app-toolkit generator."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import pytest

from hive_app_toolkit.cli.generator import ApplicationGenerator, ServiceType


@pytest.fixture
def temp_output_dir():
    """Create a temporary directory for test output."""
    temp_dir = Path(tempfile.mkdtemp())
    yield temp_dir
    # Cleanup
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.mark.asyncio
async def test_api_service_generation(temp_output_dir: Path) -> None:
    """Test generating an API service."""
    generator = ApplicationGenerator()

    config = {
        "app_name": "smoke-test-api",
        "service_type": ServiceType.API,
        "output_dir": temp_output_dir / "smoke-test-api",
        "namespace": "test",
        "port": 8000,
        "enable_database": True,
        "enable_cache": True,
        "enable_auth": False,
        "cost_limits": {"daily": 100.0, "monthly": 2000.0, "per_operation": 1.0},
        "dry_run": False,
    }

    result = await generator.generate(config)

    # Verify result structure
    assert "app_name" in result
    assert "files_created" in result
    assert len(result["files_created"]) > 0

    # Verify key files exist
    output_path = temp_output_dir / "smoke-test-api"
    assert (output_path / "src" / "smoke_test_api" / "main.py").exists()
    assert (output_path / "src" / "smoke_test_api" / "config.py").exists()
    assert (output_path / "src" / "smoke_test_api" / "api" / "main.py").exists()
    assert (output_path / "src" / "smoke_test_api" / "api" / "health.py").exists()
    assert (output_path / "tests" / "conftest.py").exists()
    assert (output_path / "tests" / "test_health.py").exists()
    assert (output_path / "tests" / "test_golden_rules.py").exists()
    assert (output_path / "src" / "smoke_test_api" / "pyproject.toml").exists()
    assert (output_path / "Dockerfile").exists()
    assert (output_path / "k8s" / "deployment.yaml").exists()
    assert (output_path / "README.md").exists()
    assert (output_path / ".gitignore").exists()


@pytest.mark.asyncio
async def test_worker_service_generation(temp_output_dir: Path) -> None:
    """Test generating a worker service."""
    generator = ApplicationGenerator()

    config = {
        "app_name": "smoke-test-worker",
        "service_type": ServiceType.WORKER,
        "output_dir": temp_output_dir / "smoke-test-worker",
        "namespace": "test",
        "port": 8000,
        "enable_database": False,
        "enable_cache": True,
        "enable_auth": False,
        "cost_limits": {},
        "dry_run": False,
    }

    result = await generator.generate(config)

    # Verify result structure
    assert "app_name" in result
    assert "files_created" in result
    assert len(result["files_created"]) > 0

    # Verify key files exist
    output_path = temp_output_dir / "smoke-test-worker"
    assert (output_path / "src" / "smoke_test_worker" / "main.py").exists()
    assert (output_path / "tests" / "test_golden_rules.py").exists()


@pytest.mark.asyncio
async def test_batch_service_generation(temp_output_dir: Path) -> None:
    """Test generating a batch processor service."""
    generator = ApplicationGenerator()

    config = {
        "app_name": "smoke-test-batch",
        "service_type": ServiceType.BATCH,
        "output_dir": temp_output_dir / "smoke-test-batch",
        "namespace": "test",
        "port": 8000,
        "enable_database": True,
        "enable_cache": False,
        "enable_auth": False,
        "cost_limits": {},
        "dry_run": False,
    }

    result = await generator.generate(config)

    # Verify result structure
    assert "app_name" in result
    assert "files_created" in result
    assert len(result["files_created"]) > 0

    # Verify key files exist
    output_path = temp_output_dir / "smoke-test-batch"
    assert (output_path / "src" / "smoke_test_batch" / "main.py").exists()
    assert (output_path / "tests" / "test_golden_rules.py").exists()


@pytest.mark.asyncio
async def test_dry_run_mode(temp_output_dir: Path) -> None:
    """Test dry-run mode does not create files."""
    generator = ApplicationGenerator()

    config = {
        "app_name": "dry-run-test",
        "service_type": ServiceType.API,
        "output_dir": temp_output_dir / "dry-run-test",
        "namespace": "test",
        "port": 8000,
        "enable_database": False,
        "enable_cache": False,
        "enable_auth": False,
        "cost_limits": {},
        "dry_run": True,
    }

    result = await generator.generate(config)

    # Verify result structure
    assert "files_created" in result
    assert len(result["files_created"]) > 0

    # Verify NO files were actually created
    output_path = temp_output_dir / "dry-run-test"
    assert not output_path.exists() or len(list(output_path.rglob("*"))) == 0


def test_pyproject_toml_validity(temp_output_dir: Path) -> None:
    """Test that generated pyproject.toml is valid TOML."""
    import asyncio

    import toml

    generator = ApplicationGenerator()

    config = {
        "app_name": "toml-test",
        "service_type": ServiceType.API,
        "output_dir": temp_output_dir / "toml-test",
        "namespace": "test",
        "port": 8000,
        "enable_database": True,
        "enable_cache": True,
        "enable_auth": False,
        "cost_limits": {},
        "dry_run": False,
    }

    asyncio.run(generator.generate(config))

    # Verify pyproject.toml is valid TOML
    pyproject_path = temp_output_dir / "toml-test" / "src" / "toml_test" / "pyproject.toml"
    assert pyproject_path.exists()

    # Parse TOML - will raise exception if invalid
    parsed = toml.load(pyproject_path)

    # Verify key sections
    assert "tool" in parsed
    assert "poetry" in parsed["tool"]
    assert "ruff" in parsed["tool"]
    assert parsed["tool"]["poetry"]["dependencies"]["python"] == "^3.11"
