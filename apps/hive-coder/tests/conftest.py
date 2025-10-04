"""
Pytest configuration and fixtures for hive-coder tests.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from hive_coder import CoderAgent


@pytest.fixture
def coder_agent() -> CoderAgent:
    """Provide a CoderAgent instance for testing"""
    return CoderAgent()


@pytest.fixture
def tmp_output_dir(tmp_path: Path) -> Path:
    """Provide a temporary output directory"""
    output_dir = tmp_path / "generated"
    output_dir.mkdir(exist_ok=True)
    return output_dir


@pytest.fixture
def sample_plan_data() -> dict:
    """Provide sample ExecutionPlan data"""
    return {
        "plan_id": "plan-test-001",
        "service_name": "test-service",
        "service_type": "api",
        "tasks": [
            {
                "task_id": "T001",
                "task_type": "scaffold",
                "description": "Generate project structure",
                "template": "api",
                "parameters": {"enable_database": True, "enable_cache": False},
                "dependencies": [],
                "estimated_duration_minutes": 5,
            },
            {
                "task_id": "T002",
                "task_type": "test_suite",
                "description": "Generate test suite",
                "parameters": {},
                "dependencies": [{"task_id": "T001", "dependency_type": "sequential"}],
                "estimated_duration_minutes": 3,
            },
        ],
        "total_estimated_duration_minutes": 8,
    }
