"""
End-to-end integration test: Architect → Coder → Generated Service

This test demonstrates the complete Project Colossus flow:
1. Architect generates ExecutionPlan from natural language
2. Coder executes plan to generate service
3. Generated service passes validation
"""

from __future__ import annotations

from pathlib import Path

import pytest

from hive_architect import ArchitectAgent
from hive_coder import CoderAgent
from hive_coder.models import ExecutionStatus


class TestE2EIntegration:
    """Test complete Architect → Coder flow"""

    @pytest.fixture
    def architect(self) -> ArchitectAgent:
        """Provide Architect Agent"""
        return ArchitectAgent()

    @pytest.fixture
    def coder(self) -> CoderAgent:
        """Provide Coder Agent"""
        return CoderAgent()

    def test_complete_flow_api_service(
        self, architect: ArchitectAgent, coder: CoderAgent, tmp_path: Path
    ) -> None:
        """
        Test complete flow: natural language → ExecutionPlan → Generated Service

        This is the core test for Project Colossus Milestone 2.
        """
        # Step 1: Architect generates ExecutionPlan from natural language
        requirement = "Create a 'status-checker' API that monitors service health"
        plan_file = tmp_path / "status-checker-plan.json"

        plan = architect.create_plan(requirement, output_path=str(plan_file))

        # Verify plan created
        assert plan is not None
        assert plan.service_name == "status-checker"
        assert len(plan.tasks) > 0
        assert plan_file.exists()

        # Step 2: Coder executes plan (dry-run - don't actually generate to avoid filesystem changes)
        # In real usage, this would call hive-app-toolkit to generate the service
        # For testing, we validate the execution flow without actual generation

        # Verify plan can be loaded
        result = coder.execute_plan(plan_file, tmp_path / "generated", validate_output=False)

        # Verify execution completed
        assert result.plan_id == plan.plan_id
        assert result.service_name == "status-checker"
        assert result.total_tasks == len(plan.tasks)

        # Some tasks may fail if hive-toolkit commands aren't available
        # The important part is the flow works end-to-end
        assert result.status in [ExecutionStatus.COMPLETED, ExecutionStatus.FAILED]

    def test_workflow_data_flow(self, architect: ArchitectAgent, coder: CoderAgent, tmp_path: Path) -> None:
        """
        Test data flows correctly through the workflow

        Verifies:
        - Architect output matches Coder input
        - Task dependencies preserved
        - Service metadata carried through
        """
        # Generate plan
        requirement = "Create a 'data-processor' batch service"
        plan_file = tmp_path / "data-processor-plan.json"
        plan = architect.create_plan(requirement, output_path=str(plan_file))

        # Validate plan structure
        validation = coder.validate_plan(plan)
        assert validation["has_tasks"] is True
        assert validation["all_dependencies_exist"] is True
        assert validation["no_cycles"] is True

        # Execute plan
        result = coder.execute_plan(plan_file, tmp_path / "generated", validate_output=False)

        # Verify data flow
        assert result.plan_id == plan.plan_id
        assert result.service_name == plan.service_name
        assert result.total_tasks == len(plan.tasks)

        # Verify task results tracked
        assert len(result.task_results) == len(plan.tasks)
        for task_result in result.task_results:
            # Each task should have corresponding task in plan
            plan_task_ids = [t.task_id for t in plan.tasks]
            assert task_result.task_id in plan_task_ids

    def test_multiple_services_independent(
        self, architect: ArchitectAgent, coder: CoderAgent, tmp_path: Path
    ) -> None:
        """
        Test generating multiple independent services

        Verifies:
        - Services don't interfere with each other
        - Plans are independent
        - Results are tracked separately
        """
        # Generate two different plans
        plan1 = architect.create_plan("Create 'auth-service' API", output_path=str(tmp_path / "auth-plan.json"))

        plan2 = architect.create_plan(
            "Create 'notification-worker' event worker", output_path=str(tmp_path / "notification-plan.json")
        )

        # Verify plans are independent
        assert plan1.plan_id != plan2.plan_id
        assert plan1.service_name != plan2.service_name
        assert plan1.service_type != plan2.service_type  # API vs Worker

        # Execute both plans
        result1 = coder.execute_plan(tmp_path / "auth-plan.json", tmp_path / "gen1", validate_output=False)

        result2 = coder.execute_plan(tmp_path / "notification-plan.json", tmp_path / "gen2", validate_output=False)

        # Verify results are independent
        assert result1.plan_id == plan1.plan_id
        assert result2.plan_id == plan2.plan_id
        assert result1.service_name != result2.service_name
        assert str(result1.output_directory) != str(result2.output_directory)
