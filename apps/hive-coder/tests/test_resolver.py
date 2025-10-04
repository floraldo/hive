"""
Tests for DependencyResolver - task ordering logic.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hive_architect.models import ExecutionPlan
from hive_coder.resolver import CyclicDependencyError, DependencyError, DependencyResolver


class TestDependencyResolver:
    """Test DependencyResolver functionality"""

    def test_resolver_initialization(self) -> None:
        """Test DependencyResolver initializes"""
        resolver = DependencyResolver()
        assert resolver is not None

    def test_resolve_order_simple(self, tmp_path: Path) -> None:
        """Test resolving simple task order"""
        plan_data = {
            "plan_id": "plan-001",
            "service_name": "test",
            "service_type": "api",
            "tasks": [
                {"task_id": "T001", "task_type": "scaffold", "description": "Scaffold", "dependencies": []},
                {
                    "task_id": "T002",
                    "task_type": "test_suite",
                    "description": "Tests",
                    "dependencies": [{"task_id": "T001"}],
                },
            ],
        }

        plan_file = tmp_path / "plan.json"
        plan_file.write_text(json.dumps(plan_data), encoding="utf-8")
        plan = ExecutionPlan.from_json_file(str(plan_file))

        resolver = DependencyResolver()
        ordered = resolver.resolve_order(plan)

        assert len(ordered) == 2
        assert ordered[0].task_id == "T001"
        assert ordered[1].task_id == "T002"

    def test_resolve_order_complex(self, tmp_path: Path) -> None:
        """Test resolving complex task dependencies"""
        plan_data = {
            "plan_id": "plan-002",
            "service_name": "test",
            "service_type": "api",
            "tasks": [
                {"task_id": "T001", "task_type": "scaffold", "description": "Scaffold", "dependencies": []},
                {
                    "task_id": "T002",
                    "task_type": "database_model",
                    "description": "DB",
                    "dependencies": [{"task_id": "T001"}],
                },
                {
                    "task_id": "T003",
                    "task_type": "api_endpoint",
                    "description": "API",
                    "dependencies": [{"task_id": "T001"}, {"task_id": "T002"}],
                },
                {
                    "task_id": "T004",
                    "task_type": "test_suite",
                    "description": "Tests",
                    "dependencies": [{"task_id": "T003"}],
                },
            ],
        }

        plan_file = tmp_path / "plan.json"
        plan_file.write_text(json.dumps(plan_data), encoding="utf-8")
        plan = ExecutionPlan.from_json_file(str(plan_file))

        resolver = DependencyResolver()
        ordered = resolver.resolve_order(plan)

        assert len(ordered) == 4
        assert ordered[0].task_id == "T001"
        # T002 before T003 (T003 depends on both T001 and T002)
        t002_idx = next(i for i, t in enumerate(ordered) if t.task_id == "T002")
        t003_idx = next(i for i, t in enumerate(ordered) if t.task_id == "T003")
        assert t002_idx < t003_idx
        # T004 comes last
        assert ordered[3].task_id == "T004"

    def test_resolve_order_cyclic_dependency(self, tmp_path: Path) -> None:
        """Test detection of circular dependencies"""
        plan_data = {
            "plan_id": "plan-cycle",
            "service_name": "test",
            "service_type": "api",
            "tasks": [
                {
                    "task_id": "T001",
                    "task_type": "scaffold",
                    "description": "Scaffold",
                    "dependencies": [{"task_id": "T002"}],
                },
                {
                    "task_id": "T002",
                    "task_type": "test_suite",
                    "description": "Tests",
                    "dependencies": [{"task_id": "T001"}],
                },
            ],
        }

        plan_file = tmp_path / "plan.json"
        plan_file.write_text(json.dumps(plan_data), encoding="utf-8")
        plan = ExecutionPlan.from_json_file(str(plan_file))

        resolver = DependencyResolver()
        with pytest.raises(CyclicDependencyError):
            resolver.resolve_order(plan)

    def test_resolve_order_missing_dependency(self, tmp_path: Path) -> None:
        """Test detection of missing dependencies"""
        plan_data = {
            "plan_id": "plan-missing",
            "service_name": "test",
            "service_type": "api",
            "tasks": [
                {
                    "task_id": "T001",
                    "task_type": "scaffold",
                    "description": "Scaffold",
                    "dependencies": [{"task_id": "T999"}],
                }
            ],
        }

        plan_file = tmp_path / "plan.json"
        plan_file.write_text(json.dumps(plan_data), encoding="utf-8")
        plan = ExecutionPlan.from_json_file(str(plan_file))

        resolver = DependencyResolver()
        with pytest.raises(DependencyError):
            resolver.resolve_order(plan)

    def test_validate_dependencies(self, tmp_path: Path) -> None:
        """Test dependency validation"""
        plan_data = {
            "plan_id": "plan-validate",
            "service_name": "test",
            "service_type": "api",
            "tasks": [
                {"task_id": "T001", "task_type": "scaffold", "description": "Scaffold", "dependencies": []},
                {
                    "task_id": "T002",
                    "task_type": "test_suite",
                    "description": "Tests",
                    "dependencies": [{"task_id": "T001"}],
                },
            ],
        }

        plan_file = tmp_path / "plan.json"
        plan_file.write_text(json.dumps(plan_data), encoding="utf-8")
        plan = ExecutionPlan.from_json_file(str(plan_file))

        resolver = DependencyResolver()
        validation = resolver.validate_dependencies(plan)

        assert validation["has_tasks"] is True
        assert validation["all_dependencies_exist"] is True
        assert validation["no_cycles"] is True
