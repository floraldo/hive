#!/usr/bin/env python3
"""
V2.1 Integration Test Suite
Tests complete system integration between Queen, AI Reviewer, and database.
"""

import sys
import time
import json
import sqlite3
import pytest
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import Mock, patch
from typing import Dict, Any

# Add paths for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "apps" / "hive-orchestrator" / "src"))
sys.path.insert(0, str(project_root / "apps" / "ai-reviewer" / "src"))
sys.path.insert(0, str(project_root / "packages" / "hive-core-db" / "src"))
sys.path.insert(0, str(project_root / "packages" / "hive-utils" / "src"))
sys.path.insert(0, str(project_root / "packages" / "hive-logging" / "src"))

import hive_core_db
from hive_orchestrator.hive_core import HiveCore
from hive_orchestrator.queen import QueenLite
from ai_reviewer.reviewer import ReviewEngine, ReviewDecision
from ai_reviewer.database_adapter import DatabaseAdapter
from hive_utils.paths import DB_PATH
from integration_helpers import (
    create_test_task,
    update_task_with_payload,
    clear_test_tasks,
    get_task_details
)


class TestQueenIntegration:
    """Test Queen orchestrator integration"""

    def test_queen_initialization(self):
        """Test that Queen can be initialized with HiveCore"""
        # Create HiveCore instance
        hive_core = HiveCore()
        assert hive_core is not None
        assert hive_core.config is not None

        # Create Queen with HiveCore
        queen = QueenLite(hive_core, live_output=False)
        assert queen is not None
        assert queen.hive is hive_core
        assert queen.config is not None

    def test_queen_task_detection(self):
        """Test Queen can detect tasks from database"""
        # Initialize database
        hive_core_db.init_db()

        # Create test task using helper
        task_id = create_test_task(
            task_id="test-queen-detection",
            title="Test Queen Integration",
            description="Verify Queen can detect tasks",
            task_type="test",
            priority=1,
            status="queued",
            assigned_worker="backend"
        )

        # Create Queen
        hive_core = HiveCore()
        queen = QueenLite(hive_core, live_output=False)

        # Get queued tasks
        tasks = hive_core_db.get_queued_tasks()
        assert len(tasks) > 0
        assert any(t['id'] == task_id for t in tasks)

        # Clean up
        hive_core_db.update_task_status(task_id, "completed")

    def test_queen_app_task_detection(self):
        """Test Queen can detect app-specific tasks"""
        hive_core = HiveCore()
        queen = QueenLite(hive_core, live_output=False)

        # Test app task detection
        app_task = {"assignee": "app:ai-reviewer:review"}
        assert queen.is_app_task(app_task) == True

        regular_task = {"assignee": "backend"}
        assert queen.is_app_task(regular_task) == False

        # Test app assignee parsing
        app_name, task_name = queen.parse_app_assignee("app:ai-reviewer:review")
        assert app_name == "ai-reviewer"
        assert task_name == "review"


class TestAIReviewerIntegration:
    """Test AI Reviewer integration"""

    def test_reviewer_initialization(self):
        """Test ReviewEngine initialization with mock mode"""
        engine = ReviewEngine(mock_mode=True)
        assert engine is not None
        assert engine.robust_claude.mock_mode == True
        assert engine.thresholds["approve_threshold"] == 80.0
        assert engine.thresholds["reject_threshold"] == 40.0

    def test_database_adapter(self):
        """Test DatabaseAdapter can interact with hive_core_db"""
        # Initialize database
        hive_core_db.init_db()

        # Create adapter
        adapter = DatabaseAdapter()

        # Create test task in review_pending status using helper
        task_id = create_test_task(
            task_id="test-review-adapter",
            title="Test Review Task",
            description="Code for review",
            task_type="review",
            priority=1,
            status="review_pending"
        )

        # Test adapter can find pending reviews
        pending = adapter.get_pending_reviews(limit=10)
        assert any(t['id'] == task_id for t in pending)

        # Test status update
        success = adapter.update_task_status(
            task_id,
            "approved",
            {"review_score": 85, "decision": "approve"}
        )
        assert success == True

        # Verify status was updated
        task = hive_core_db.get_task(task_id)
        assert task['status'] == "approved"

    def test_review_workflow(self):
        """Test complete review workflow"""
        # Initialize components
        hive_core_db.init_db()
        engine = ReviewEngine(mock_mode=True)
        adapter = DatabaseAdapter()

        # Create test task with code using helper
        task_id = create_test_task(
            task_id="test-review-workflow",
            title="Review Test Code",
            description="Test the review workflow",
            task_type="development",
            priority=1,
            status="review_pending",
            payload={
                "code_files": {
                    "main.py": "def hello():\n    '''Say hello'''\n    return 'Hello, World!'\n"
                }
            }
        )

        # Perform review
        code_files = adapter.get_task_code_files(task_id)
        assert code_files is not None

        result = engine.review_task(
            task_id=task_id,
            task_description="Test task",
            code_files=code_files
        )

        assert result is not None
        assert result.task_id == task_id
        assert isinstance(result.decision, ReviewDecision)
        assert result.metrics.overall_score >= 0

        # Update status based on decision
        status_map = {
            ReviewDecision.APPROVE: "approved",
            ReviewDecision.REJECT: "rejected",
            ReviewDecision.REWORK: "rework_needed",
            ReviewDecision.ESCALATE: "escalated"
        }

        new_status = status_map[result.decision]
        success = adapter.update_task_status(task_id, new_status, result.to_dict())
        assert success == True


class TestSystemIntegration:
    """Test complete system integration"""

    def setup_method(self):
        """Setup for each test"""
        # Initialize database
        hive_core_db.init_db()

        # Clear any existing test tasks
        clear_test_tasks()

    def test_happy_path_integration(self):
        """Test happy path: task creation → review → approval"""
        # Create high-quality task
        task_id = f"integration-test-happy-{datetime.now().strftime('%H%M%S')}"
        create_test_task(
            task_id=task_id,
            title="High Quality Implementation",
            description="Well-written code with tests",
            task_type="development",
            priority=1,
            status="review_pending",
            payload={
                "code_files": {
                    "calculator.py": '''
"""Calculator module with basic operations."""

def add(x: float, y: float) -> float:
    """Add two numbers.

    Args:
        x: First number
        y: Second number

    Returns:
        Sum of x and y
    """
    return x + y

def multiply(x: float, y: float) -> float:
    """Multiply two numbers.

    Args:
        x: First number
        y: Second number

    Returns:
        Product of x and y
    """
    return x * y
''',
                    "test_calculator.py": '''
"""Tests for calculator module."""

import pytest
from calculator import add, multiply

def test_add():
    """Test addition function."""
    assert add(2, 3) == 5
    assert add(-1, 1) == 0
    assert add(0.5, 0.5) == 1.0

def test_multiply():
    """Test multiplication function."""
    assert multiply(2, 3) == 6
    assert multiply(-1, 5) == -5
    assert multiply(0.5, 4) == 2.0
'''
                },
                "test_results": {
                    "passed": True,
                    "coverage": 100
                }
            }
        )

        # Initialize components
        engine = ReviewEngine(mock_mode=True)
        adapter = DatabaseAdapter()

        # Verify task is in review_pending
        task = hive_core_db.get_task(task_id)
        assert task['status'] == "review_pending"

        # Process review
        pending_tasks = adapter.get_pending_reviews()
        review_task = next((t for t in pending_tasks if t['id'] == task_id), None)
        assert review_task is not None

        # Get task artifacts
        code_files = adapter.get_task_code_files(task_id)
        test_results = adapter.get_test_results(task_id)

        # Perform review
        result = engine.review_task(
            task_id=task_id,
            task_description=review_task['description'],
            code_files=code_files,
            test_results=test_results
        )

        # Verify high score for good code
        assert result.metrics.overall_score > 80
        assert result.decision == ReviewDecision.APPROVE

        # Update task status
        success = adapter.update_task_status(task_id, "approved", result.to_dict())
        assert success == True

        # Verify final state
        final_task = hive_core_db.get_task(task_id)
        assert final_task['status'] == "approved"

        # Verify review data was stored
        task_details = get_task_details(task_id)
        if task_details and task_details.get('payload'):
            assert 'review_decision' in task_details['payload']
            assert task_details['payload']['review_decision'] == "approve"

    def test_escalation_path_integration(self):
        """Test escalation path: borderline task → review → escalation"""
        # Create borderline task
        task_id = f"integration-test-escalate-{datetime.now().strftime('%H%M%S')}"
        create_test_task(
            task_id=task_id,
            title="Borderline Implementation",
            description="Code with some issues",
            task_type="development",
            priority=2,
            status="review_pending",
            payload={
                "code_files": {
                    "processor.py": '''
# Quick implementation
def process_data(data):
    # TODO: Add validation
    result = []
    for item in data:
        # Process each item
        if item > 0:
            result.append(item * 2)
    return result

def calculate(x, y):
    try:
        return x / y
    except:
        return None  # TODO: Better error handling
'''
                },
                "test_results": {
                    "passed": True,
                    "coverage": 45
                }
            }
        )

        # Initialize components
        engine = ReviewEngine(mock_mode=True)
        adapter = DatabaseAdapter()

        # Process review
        code_files = adapter.get_task_code_files(task_id)
        test_results = adapter.get_test_results(task_id)

        result = engine.review_task(
            task_id=task_id,
            task_description="Borderline quality code",
            code_files=code_files,
            test_results=test_results
        )

        # Verify medium score triggers rework or escalation
        assert 40 <= result.metrics.overall_score <= 60
        assert result.decision in [ReviewDecision.REWORK, ReviewDecision.ESCALATE]

        # Update task status
        if result.decision == ReviewDecision.ESCALATE:
            new_status = "escalated"
        else:
            new_status = "rework_needed"

        success = adapter.update_task_status(task_id, new_status, result.to_dict())
        assert success == True

        # Verify final state
        final_task = hive_core_db.get_task(task_id)
        assert final_task['status'] in ["escalated", "rework_needed"]

    def test_rejection_path_integration(self):
        """Test rejection path: poor quality → review → rejection"""
        # Create poor quality task
        task_id = f"integration-test-reject-{datetime.now().strftime('%H%M%S')}"
        create_test_task(
            task_id=task_id,
            title="Poor Implementation",
            description="Code with serious issues",
            task_type="development",
            priority=3,
            status="review_pending",
            payload={
                "code_files": {
                    "dangerous.py": '''
def run_command(user_input):
    # Execute arbitrary commands
    eval(user_input)
    exec(user_input)

password = "admin123"  # Hardcoded credentials

def process():
    try:
        # Complex nested logic
        x = getData()
        if x:
            if x > 0:
                if x > 10:
                    if x > 100:
                        doSomething()
    except:
        pass  # Ignore all errors
'''
                },
                "test_results": None  # No tests
            }
        )

        # Initialize components
        engine = ReviewEngine(mock_mode=True)
        adapter = DatabaseAdapter()

        # Process review
        code_files = adapter.get_task_code_files(task_id)

        result = engine.review_task(
            task_id=task_id,
            task_description="Poor quality code",
            code_files=code_files,
            test_results=None
        )

        # Verify low score triggers rejection
        assert result.metrics.overall_score < 40
        assert result.decision in [ReviewDecision.REJECT, ReviewDecision.ESCALATE]
        assert len(result.issues) > 0  # Should have identified issues

        # Update task status
        if result.decision == ReviewDecision.REJECT:
            new_status = "rejected"
        else:
            new_status = "escalated"

        success = adapter.update_task_status(task_id, new_status, result.to_dict())
        assert success == True

        # Verify final state
        final_task = hive_core_db.get_task(task_id)
        assert final_task['status'] in ["rejected", "escalated"]

    def test_queen_reviewer_coordination(self):
        """Test Queen and AI Reviewer can work together"""
        # Initialize system
        hive_core = HiveCore()
        queen = QueenLite(hive_core, live_output=False)
        engine = ReviewEngine(mock_mode=True)
        adapter = DatabaseAdapter()

        # Create task that needs review
        task_id = f"integration-test-coord-{datetime.now().strftime('%H%M%S')}"
        create_test_task(
            task_id=task_id,
            title="Coordination Test",
            description="Test Queen-Reviewer coordination",
            task_type="development",
            priority=1,
            status="completed",  # Task completed by worker
            current_phase="test",
            assigned_worker="backend",
            payload={
                "code_files": {
                    "feature.py": "def feature():\n    return 'implemented'\n"
                }
            }
        )

        # Queen should move to review_pending
        hive_core_db.update_task_status(task_id, "review_pending")

        # AI Reviewer should pick it up
        pending = adapter.get_pending_reviews()
        assert any(t['id'] == task_id for t in pending)

        # Process review
        code_files = adapter.get_task_code_files(task_id)
        result = engine.review_task(
            task_id=task_id,
            task_description="Test task",
            code_files=code_files
        )

        # Update status
        status_map = {
            ReviewDecision.APPROVE: "approved",
            ReviewDecision.REJECT: "rejected",
            ReviewDecision.REWORK: "rework_needed",
            ReviewDecision.ESCALATE: "escalated"
        }

        new_status = status_map[result.decision]
        adapter.update_task_status(task_id, new_status, result.to_dict())

        # Verify coordination completed
        final_task = hive_core_db.get_task(task_id)
        assert final_task['status'] in ["approved", "rejected", "rework_needed", "escalated"]


def main():
    """Run integration tests"""
    print("=" * 70)
    print("V2.1 Integration Test Suite")
    print("=" * 70)

    # Run pytest with verbose output
    import pytest
    sys.exit(pytest.main([__file__, "-v", "-s"]))


if __name__ == "__main__":
    main()