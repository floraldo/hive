"""Tests for Architect Agent - The Brain of Project Colossus.

Tests the complete flow from natural language → execution plan.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hive_architect.agent import ArchitectAgent
from hive_architect.models import ServiceType, TaskType


class TestArchitectAgent:
    """Test suite for Architect Agent"""

    @pytest.fixture
    def agent(self) -> ArchitectAgent:
        """Create Architect Agent instance"""
        return ArchitectAgent()

    @pytest.fixture
    def test_requirements(self) -> list[str]:
        """Sample requirements for testing"""
        return [
            "Create a 'feedback-service' API that stores user feedback",
            "Build a 'notification-worker' that processes email notifications",
            "Generate a 'report-processor' batch job that runs daily analytics",
            "Create a 'user-service' REST API with authentication and profiles",
            "Build an 'event-handler' worker to process webhook events",
        ]

    def test_parse_api_requirement(self, agent: ArchitectAgent) -> None:
        """Test parsing API service requirement"""
        requirement = "Create a 'feedback-service' API that stores user feedback"

        parsed = agent.parse_requirement(requirement)

        assert parsed.service_name == "feedback-service"
        assert parsed.service_type == ServiceType.API
        assert parsed.enable_database is True
        assert len(parsed.features) > 0
        assert parsed.confidence_score > 0.5

    def test_parse_worker_requirement(self, agent: ArchitectAgent) -> None:
        """Test parsing worker service requirement"""
        requirement = "Build a 'notification-worker' that processes email notifications"

        parsed = agent.parse_requirement(requirement)

        assert parsed.service_name == "notification-worker"
        assert parsed.service_type == ServiceType.WORKER
        assert "process" in " ".join(parsed.features).lower()

    def test_parse_batch_requirement(self, agent: ArchitectAgent) -> None:
        """Test parsing batch job requirement"""
        requirement = "Generate a 'report-processor' batch job that runs daily analytics"

        parsed = agent.parse_requirement(requirement)

        assert parsed.service_name == "report-processor"
        assert parsed.service_type == ServiceType.BATCH

    def test_generate_plan(self, agent: ArchitectAgent) -> None:
        """Test execution plan generation"""
        requirement = "Create a 'feedback-service' API that stores user feedback"

        parsed = agent.parse_requirement(requirement)
        plan = agent.generate_plan(parsed)

        assert plan.service_name == "feedback-service"
        assert plan.service_type == "api"
        assert len(plan.tasks) > 0
        assert plan.total_estimated_duration_minutes > 0

    def test_plan_has_scaffold_task(self, agent: ArchitectAgent) -> None:
        """Test that plan includes scaffold task"""
        requirement = "Create a 'test-service' API"

        plan = agent.create_plan(requirement)

        scaffold_tasks = [t for t in plan.tasks if t.task_type == TaskType.SCAFFOLD]
        assert len(scaffold_tasks) == 1
        assert scaffold_tasks[0].task_id == "T001"

    def test_plan_has_database_task_when_needed(self, agent: ArchitectAgent) -> None:
        """Test database task creation when storage is needed"""
        requirement = "Create a 'user-service' API that stores user profiles"

        plan = agent.create_plan(requirement)

        db_tasks = [t for t in plan.tasks if t.task_type == TaskType.DATABASE_MODEL]
        assert len(db_tasks) > 0

    def test_plan_has_test_task(self, agent: ArchitectAgent) -> None:
        """Test that plan includes test generation"""
        requirement = "Create a 'test-service' API"

        plan = agent.create_plan(requirement)

        test_tasks = [t for t in plan.tasks if t.task_type == TaskType.TEST_SUITE]
        assert len(test_tasks) == 1

    def test_plan_has_documentation_task(self, agent: ArchitectAgent) -> None:
        """Test that plan includes documentation"""
        requirement = "Create a 'test-service' API"

        plan = agent.create_plan(requirement)

        doc_tasks = [t for t in plan.tasks if t.task_type == TaskType.DOCUMENTATION]
        assert len(doc_tasks) == 1

    def test_task_dependencies_valid(self, agent: ArchitectAgent) -> None:
        """Test that task dependencies are properly structured"""
        requirement = "Create a 'test-service' API that stores data"

        plan = agent.create_plan(requirement)
        validation = agent.validate_plan(plan)

        assert validation["dependencies_valid"] is True

    def test_plan_within_time_budget(self, agent: ArchitectAgent) -> None:
        """Test that plan meets 60-minute target"""
        requirement = "Create a 'simple-service' API"

        plan = agent.create_plan(requirement)

        assert plan.total_estimated_duration_minutes < 60

    def test_plan_to_json_file(
        self,
        agent: ArchitectAgent,
        tmp_path: Path,
    ) -> None:
        """Test saving plan to JSON file"""
        requirement = "Create a 'test-service' API"
        output_path = tmp_path / "plan.json"

        _plan = agent.create_plan(requirement, output_path=str(output_path))

        assert output_path.exists()

        # Verify JSON is valid
        with open(output_path) as f:
            data = json.load(f)
            assert data["service_name"] == "test-service"
            assert "tasks" in data

    def test_all_sample_requirements(
        self,
        agent: ArchitectAgent,
        test_requirements: list[str],
    ) -> None:
        """Test agent with all 5 sample requirements"""
        results = []

        for requirement in test_requirements:
            parsed = agent.parse_requirement(requirement)
            plan = agent.create_plan(requirement)
            validation = agent.validate_plan(plan)

            results.append(
                {
                    "requirement": requirement,
                    "service_name": parsed.service_name,
                    "service_type": parsed.service_type,
                    "task_count": len(plan.tasks),
                    "duration_minutes": plan.total_estimated_duration_minutes,
                    "valid": all(validation.values()),
                },
            )

        # All requirements should parse successfully
        assert all(r["valid"] for r in results)

        # All should be under 60 minutes
        assert all(r["duration_minutes"] < 60 for r in results)

        # Print summary
        for result in results:
            print(
                f"\n{result['service_name']} ({result['service_type']}): "
                f"{result['task_count']} tasks, {result['duration_minutes']} min",
            )
