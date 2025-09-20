#!/usr/bin/env python3
"""
Test script for the Human-AI Interface escalation system.
Creates test tasks that will trigger escalation for demonstration.
"""

import sys
import json
import sqlite3
from pathlib import Path
from datetime import datetime
import uuid

# Add path for imports
sys.path.insert(0, str(Path(__file__).parents[1] / "packages" / "hive-core-db" / "src"))
sys.path.insert(0, str(Path(__file__).parents[1] / "apps" / "ai-reviewer" / "src"))

from hive_core_db.database import get_connection, TaskStatus
from ai_reviewer.reviewer import ReviewEngine, QualityMetrics, ReviewDecision


def create_test_escalation_task():
    """Create a task that will trigger escalation when reviewed."""
    conn = get_connection()
    cursor = conn.cursor()

    task_id = str(uuid.uuid4())

    # Create a task with borderline quality code that will escalate
    borderline_code = {
        "borderline.py": '''
def process_data(data):
    """Process data with questionable practices."""
    # TODO: This needs major refactoring
    result = []

    # Security concern but not critical
    user_input = input("Enter command: ")
    if user_input != "dangerous":
        # Complex nested logic
        for item in data:
            if item > 0:
                if item < 100:
                    if item % 2 == 0:
                        result.append(item * 2)

    # Poor error handling
    try:
        return result[0]
    except:
        return None
''',
        "test_borderline.py": '''
def test_something():
    """Minimal test coverage."""
    assert True
'''
    }

    # Simulate AI review
    engine = ReviewEngine()
    result = engine.review_task(
        task_id=task_id,
        task_description="Process user data with validation",
        code_files=borderline_code,
        test_results={"passed": True, "coverage": 30}
    )

    # Insert task into database
    cursor.execute("""
        INSERT INTO tasks (id, title, description, task_type, status, priority, result_data, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        task_id,
        "Borderline Quality Task",
        "Process user data with validation - AI uncertain about quality",
        "general",
        TaskStatus.ESCALATED.value,
        3,
        json.dumps(result.to_dict()),
        datetime.now().isoformat(),
        datetime.now().isoformat()
    ))

    conn.commit()
    print(f"✓ Created escalated task: {task_id}")
    print(f"  Decision: {result.decision.value}")
    print(f"  Score: {result.metrics.overall_score:.0f}")
    print(f"  Reason: {result.escalation_reason}")

    return task_id


def create_critical_escalation_task():
    """Create a critical task requiring immediate human review."""
    conn = get_connection()
    cursor = conn.cursor()

    task_id = str(uuid.uuid4())

    # Create a task with security issues
    security_code = {
        "auth.py": '''
import pickle
import os

def authenticate(user_data):
    """Authentication with security issues."""
    # Critical: Using eval on user input
    eval(user_data['command'])

    # Hardcoded credentials
    password = "admin123"

    # Unsafe deserialization
    with open('user.pkl', 'rb') as f:
        user = pickle.load(f)

    # Command injection risk
    os.system(f"echo {user_data['name']}")

    return user
'''
    }

    # Simulate AI review
    engine = ReviewEngine()
    result = engine.review_task(
        task_id=task_id,
        task_description="Implement secure authentication",
        code_files=security_code,
        test_results=None
    )

    # Force escalation for demonstration
    if result.decision != ReviewDecision.ESCALATE:
        result.decision = ReviewDecision.ESCALATE
        result.escalation_reason = "Critical security vulnerabilities require immediate human review"
        result.confusion_points = [
            "Multiple severe security issues detected",
            "eval() usage on user input",
            "Hardcoded passwords",
            "Command injection vulnerabilities"
        ]

    # Insert task into database
    cursor.execute("""
        INSERT INTO tasks (id, title, description, task_type, status, priority, result_data, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        task_id,
        "CRITICAL: Security Review Required",
        "Authentication system with multiple security concerns",
        "security",
        TaskStatus.ESCALATED.value,
        10,  # Highest priority
        json.dumps(result.to_dict()),
        datetime.now().isoformat(),
        datetime.now().isoformat()
    ))

    conn.commit()
    print(f"🚨 Created critical escalation: {task_id}")
    print(f"  Priority: 10 (CRITICAL)")
    print(f"  Issues: {len(result.issues)}")
    print(f"  Reason: {result.escalation_reason}")

    return task_id


def create_complex_decision_task():
    """Create a task with conflicting quality signals."""
    conn = get_connection()
    cursor = conn.cursor()

    task_id = str(uuid.uuid4())

    # Code with high test coverage but poor quality
    complex_code = {
        "calculator.py": '''
def c(a,b):return a+b
def s(a,b):return a-b
def m(a,b):return a*b
def d(a,b):return a/b if b else 0
''',
        "test_calculator.py": '''
import pytest
from calculator import c, s, m, d

def test_addition():
    assert c(1, 2) == 3
    assert c(-1, 1) == 0
    assert c(0, 0) == 0

def test_subtraction():
    assert s(5, 3) == 2
    assert s(0, 1) == -1

def test_multiplication():
    assert m(2, 3) == 6
    assert m(0, 5) == 0

def test_division():
    assert d(6, 2) == 3
    assert d(5, 0) == 0

def test_edge_cases():
    assert c(1.5, 2.5) == 4.0
    assert s(-10, -5) == -5
    assert m(-2, 3) == -6
    assert d(10, 3) == pytest.approx(3.333, 0.01)
'''
    }

    # Simulate AI review
    engine = ReviewEngine()
    result = engine.review_task(
        task_id=task_id,
        task_description="Calculator with comprehensive testing",
        code_files=complex_code,
        test_results={"passed": True, "coverage": 95}
    )

    # Ensure it's escalated for the demo
    result.decision = ReviewDecision.ESCALATE
    result.escalation_reason = "Conflicting quality signals: excellent tests but terrible code quality"
    result.confusion_points = [
        "95% test coverage but unreadable code",
        "Single-letter function names",
        "No documentation despite comprehensive tests",
        "High variance between test quality and code quality"
    ]

    # Insert task into database
    cursor.execute("""
        INSERT INTO tasks (id, title, description, task_type, status, priority, result_data, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        task_id,
        "Conflicting Quality Signals",
        "Well-tested but poorly written calculator",
        "general",
        TaskStatus.ESCALATED.value,
        5,
        json.dumps(result.to_dict()),
        datetime.now().isoformat(),
        datetime.now().isoformat()
    ))

    conn.commit()
    print(f"⚖️  Created complex decision task: {task_id}")
    print(f"  Test Coverage: 95%")
    print(f"  Code Quality: Poor")
    print(f"  Reason: {result.escalation_reason}")

    return task_id


def main():
    """Create test escalation tasks and show how to review them."""
    print("\n" + "="*60)
    print("HIVE ESCALATION SYSTEM TEST")
    print("="*60)
    print("\nCreating test tasks that require human review...\n")

    # Create various escalation scenarios
    task1 = create_test_escalation_task()
    task2 = create_critical_escalation_task()
    task3 = create_complex_decision_task()

    print("\n" + "-"*60)
    print("TEST TASKS CREATED SUCCESSFULLY")
    print("-"*60)

    print("\n📋 Next Steps:")
    print("\n1. View escalated tasks in the dashboard:")
    print("   python -m hive_orchestrator.dashboard")
    print("\n2. List all escalated tasks:")
    print("   hive list-escalated")
    print("\n3. Review a specific task:")
    print(f"   hive review-escalated {task1}")
    print("\n4. Start AI Reviewer to process more tasks:")
    print("   cd apps/ai-reviewer && ./start_reviewer.sh")

    print("\n" + "="*60)
    print("The escalation system is now ready for testing!")
    print("You are now the senior architect handling edge cases.")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()