"""Tests for CoderAgent - main orchestrator.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hive_architect.models import ExecutionPlan
from hive_coder import CoderAgent
from hive_coder.models import ExecutionStatus


class TestCoderAgent:
    """Test CoderAgent functionality"""

    def test_agent_initialization(self, coder_agent: CoderAgent) -> None:
        """Test CoderAgent initializes correctly"""
        assert coder_agent is not None
        assert coder_agent.resolver is not None
        assert coder_agent.validator is not None

    def test_load_plan(self, coder_agent: CoderAgent, tmp_path: Path, sample_plan_data: dict) -> None:
        """Test loading ExecutionPlan from JSON file"""
        # Create plan file
        plan_file = tmp_path / "test_plan.json"
        plan_file.write_text(json.dumps(sample_plan_data), encoding="utf-8")

        # Load plan
        plan = coder_agent._load_plan(plan_file)

        assert plan.plan_id == "plan-test-001"
        assert plan.service_name == "test-service"
        assert len(plan.tasks) == 2

    def test_load_plan_file_not_found(self, coder_agent: CoderAgent) -> None:
        """Test loading non-existent plan file raises error"""
        with pytest.raises(FileNotFoundError):
            coder_agent._load_plan("nonexistent.json")

    def test_validate_plan(self, coder_agent: CoderAgent, tmp_path: Path, sample_plan_data: dict) -> None:
        """Test plan validation"""
        # Create and load plan
        plan_file = tmp_path / "test_plan.json"
        plan_file.write_text(json.dumps(sample_plan_data), encoding="utf-8")
        plan = ExecutionPlan.from_json_file(str(plan_file))

        # Validate
        validation = coder_agent.validate_plan(plan)

        assert validation["has_tasks"] is True
        assert validation["all_dependencies_exist"] is True
        assert validation["no_cycles"] is True

    def test_validate_plan_invalid_dependency(self, coder_agent: CoderAgent, tmp_path: Path) -> None:
        """Test plan validation with invalid dependency"""
        plan_data = {
            "plan_id": "plan-invalid",
            "service_name": "test-service",
            "service_type": "api",
            "tasks": [
                {
                    "task_id": "T001",
                    "task_type": "scaffold",
                    "description": "Generate project",
                    "dependencies": [{"task_id": "T999", "dependency_type": "sequential"}],
                },
            ],
        }

        plan_file = tmp_path / "invalid_plan.json"
        plan_file.write_text(json.dumps(plan_data), encoding="utf-8")
        plan = ExecutionPlan.from_json_file(str(plan_file))

        validation = coder_agent.validate_plan(plan)
        assert validation["all_dependencies_exist"] is False

    def test_execute_plan_basic(self, coder_agent: CoderAgent, tmp_output_dir: Path, tmp_path: Path) -> None:
        """Test basic plan execution without actual code generation"""
        # Create minimal plan (just for testing flow)
        plan_data = {
            "plan_id": "plan-basic-test",
            "service_name": "basic-test-service",
            "service_type": "api",
            "tasks": [
                {
                    "task_id": "T001",
                    "task_type": "documentation",
                    "description": "Add documentation",
                    "parameters": {},
                    "dependencies": [],
                },
            ],
        }

        plan_file = tmp_path / "basic_plan.json"
        plan_file.write_text(json.dumps(plan_data), encoding="utf-8")

        # Execute plan (validation will fail since no code generated, but tests execution flow)
        result = coder_agent.execute_plan(plan_file, tmp_output_dir, validate_output=False)

        assert result.plan_id == "plan-basic-test"
        assert result.service_name == "basic-test-service"
        assert result.total_tasks == 1
        assert result.status in [ExecutionStatus.COMPLETED, ExecutionStatus.FAILED]

    def test_execution_result_summary(self, coder_agent: CoderAgent, tmp_output_dir: Path, tmp_path: Path) -> None:
        """Test ExecutionResult summary generation"""
        plan_data = {
            "plan_id": "plan-summary-test",
            "service_name": "summary-test",
            "service_type": "api",
            "tasks": [
                {"task_id": "T001", "task_type": "documentation", "description": "Docs", "dependencies": []},
            ],
        }

        plan_file = tmp_path / "summary_plan.json"
        plan_file.write_text(json.dumps(plan_data), encoding="utf-8")

        result = coder_agent.execute_plan(plan_file, tmp_output_dir, validate_output=False)
        summary = result.to_summary_dict()

        assert "plan_id" in summary
        assert "service_name" in summary
        assert "status" in summary
        assert "tasks" in summary
        assert summary["tasks"]["total"] == 1
