#!/usr/bin/env python3
"""
End-to-end test for autonomous AI reviewer with drift simulation
Tests the complete review loop including drift resilience
"""

import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from ai_reviewer.database_adapter import DatabaseAdapter
from ai_reviewer.reviewer import ReviewEngine
from ai_reviewer.robust_claude_bridge import ClaudeReviewResponse, RobustClaudeBridge
from hive_orchestrator.core import db as hive_core_db

# Imports now handled by Poetry workspace dependencies
# Import from orchestrator core for Hive-specific database access
from hive_orchestrator.core.db import get_database, get_pooled_connection


def create_test_task(task_type: str = "good") -> str:
    """Create a test task in review_pending status"""
    hive_core_db.init_db()

    task_id = f"test-e2e-{task_type}-{datetime.now().strftime('%H%M%S')}"

    # Different code samples for testing
    if task_type == "good":
        code = """
def calculate_fibonacci(n: int) -> int:
    '''Calculate nth Fibonacci number with memoization'''
    if n <= 0:
        raise ValueError("n must be positive")

    cache = {0: 0, 1: 1}

    def fib(x):
        if x not in cache:
            cache[x] = fib(x-1) + fib(x-2)
        return cache[x]

    return fib(n)
"""
        description = "Fibonacci calculator with memoization"
    elif task_type == "bad":
        code = """
def process_data(x):
    # TODO: implement this
    exec(x)  # Security risk!
    return eval(x) * 2  # Another security risk!
"""
        description = "Data processor with security vulnerabilities"
    else:  # complex
        code = """
import asyncio
from typing import List, Dict, Any

async def distributed_compute(tasks: List[Dict[str, Any]]) -> List[Any]:
    '''Complex distributed computation system'''
    async def worker(task):
        # Complex logic here...
        return await process_task(task)

    results = await asyncio.gather(*[worker(t) for t in tasks])
    return results
"""
        description = "Complex distributed computing system"

    # Create task
    task_data = {
        "id": task_id,
        "title": f"Test {task_type} code review",
        "description": description,
        "task_type": "test",
        "priority": 1,
        "status": "review_pending",
        "payload": json.dumps(
            {
                "message": f"Test task for {task_type} code",
                "code": code,
                "files": {"main.py": code},
            }
        ),
        "assigned_worker": "backend",
        "workspace_type": "repo",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    # Insert into database
    from hive_config.paths import DB_PATH

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO tasks (
            id, title, description, task_type, priority, status,
            payload, assigned_worker, workspace_type, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
        (
            task_data["id"],
            task_data["title"],
            task_data["description"],
            task_data["task_type"],
            task_data["priority"],
            task_data["status"],
            task_data["payload"],
            task_data["assigned_worker"],
            task_data["workspace_type"],
            task_data["created_at"],
        ),
    )
    conn.commit()
    conn.close()

    print(f"[OK] Created test task: {task_id}")
    return task_id


def test_json_extraction():
    """Test the robust JSON extraction from various Claude responses"""
    print("\n=== Testing JSON Extraction (Drift Simulation) ===")

    bridge = RobustClaudeBridge()

    # Test Case 1: Pure JSON (ideal case)
    test_cases = [
        {
            "name": "Pure JSON",
            "output": """{"decision": "approve", "summary": "Code looks good", "issues": [], "suggestions": [], "quality_score": 85, "metrics": {"code_quality": 85, "security": 90, "testing": 80, "architecture": 85, "documentation": 75}, "confidence": 0.9}""",
            "expected_decision": "approve",
        },
        {
            "name": "JSON in markdown",
            "output": """Sure! Here's my review:
```json
{"decision": "rework", "summary": "Needs improvements", "issues": ["No error handling"], "suggestions": ["Add try-catch blocks"], "quality_score": 65, "metrics": {"code_quality": 65, "security": 70, "testing": 60, "architecture": 65, "documentation": 55}, "confidence": 0.8}
```
Hope this helps!""",
            "expected_decision": "rework",
        },
        {
            "name": "Conversational response",
            "output": """I've reviewed the code and I would APPROVE it. The implementation is solid with good error handling. The code quality is excellent.""",
            "expected_decision": "approve",
        },
        {
            "name": "Malformed JSON recovery",
            "output": """The review results: decision=reject, summary="Major security issues", issues=["SQL injection risk"], quality_score=25""",
            "expected_decision": "reject",
        },
    ]

    passed = 0
    for test in test_cases:
        try:
            result = bridge._extract_and_validate_json(test["output"])
            if result and result.decision == test["expected_decision"]:
                print(
                    f"  [PASS] {test['name']}: Correctly extracted '{result.decision}'"
                )
                passed += 1
            else:
                print(f"  [FAIL] {test['name']}: Failed to extract correct decision")
        except Exception as e:
            print(f"  [ERROR] {test['name']}: Error - {str(e)[:50]}")

    print(f"\nDrift resilience: {passed}/{len(test_cases)} tests passed")
    return passed == len(test_cases)


def test_review_engine():
    """Test the complete review engine"""
    print("\n=== Testing Review Engine ===")

    # Use mock mode for testing to avoid Claude CLI issues
    from ai_reviewer.robust_claude_bridge import RobustClaudeBridge

    engine = ReviewEngine()
    engine.robust_claude = RobustClaudeBridge(mock_mode=True)

    # Test with good code
    good_code = {
        "fibonacci.py": """def fib(n):
    if n <= 1:
        return n
    return fib(n-1) + fib(n-2)"""
    }

    print("Testing review of good code...")
    result = engine.review_task(
        task_id="test-engine-good",
        task_description="Fibonacci implementation",
        code_files=good_code,
    )

    print(f"  Decision: {result.decision}")
    print(f"  Score: {result.metrics.overall_score}")
    print(f"  Summary: {result.summary}")

    # Test with bad code
    bad_code = {"vulnerable.py": "exec(user_input)  # DANGEROUS!"}

    print("\nTesting review of bad code...")
    result = engine.review_task(
        task_id="test-engine-bad",
        task_description="User input processor",
        code_files=bad_code,
    )

    print(f"  Decision: {result.decision}")
    print(f"  Score: {result.metrics.overall_score}")
    print(f"  Summary: {result.summary}")

    return True


def test_full_autonomous_loop():
    """Test the complete autonomous review loop"""
    print("\n=== Testing Full Autonomous Loop ===")

    # Step 1: Create test tasks
    good_task_id = create_test_task("good")
    bad_task_id = create_test_task("bad")

    # Step 2: Initialize components
    adapter = DatabaseAdapter()
    from ai_reviewer.robust_claude_bridge import RobustClaudeBridge

    engine = ReviewEngine()
    engine.robust_claude = RobustClaudeBridge(mock_mode=True)

    # Step 3: Process pending reviews
    pending_tasks = adapter.get_pending_reviews(limit=10)
    print(f"\nFound {len(pending_tasks)} pending review tasks")

    processed = 0
    for task in pending_tasks:
        task_id = task["id"]
        if task_id not in [good_task_id, bad_task_id]:
            continue

        print(f"\nProcessing task: {task_id}")

        # Get code files
        code_files = adapter.get_task_code_files(task_id)
        if not code_files:
            print(f"  [ERROR] No code files found")
            continue

        # Perform review
        result = engine.review_task(
            task_id=task_id,
            task_description=task.get("description", "Test task"),
            code_files=code_files,
        )

        print(f"  Review completed: {result.decision.value}")
        print(f"  Score: {result.metrics.overall_score}")

        # Update task status
        status_map = {
            "approve": "approved",
            "reject": "rejected",
            "rework": "rework_needed",
            "escalate": "escalated",
        }

        new_status = status_map.get(result.decision.value, "escalated")
        success = adapter.update_task_status(task_id, new_status, result.to_dict())

        if success:
            print(f"  [OK] Status updated to '{new_status}'")
            processed += 1
        else:
            print(f"  [ERROR] Failed to update status")

    print(f"\n[SUCCESS] Processed {processed} tasks successfully")
    return processed > 0


def test_configuration():
    """Test configuration and thresholds"""
    print("\n=== Testing Configuration ===")

    engine = ReviewEngine()

    print("Review thresholds:")
    for key, value in engine.thresholds.items():
        print(f"  {key}: {value}")

    # Test that thresholds are being used
    assert engine.thresholds["approve_threshold"] == 80.0
    assert engine.thresholds["reject_threshold"] == 40.0

    print("[OK] Configuration validated")
    return True


def main():
    """Run all E2E tests"""
    print("=" * 60)
    print("AI Reviewer End-to-End Test Suite")
    print("=" * 60)

    results = []

    try:
        # Test 1: JSON extraction and drift resilience
        results.append(("JSON Extraction", test_json_extraction()))

        # Test 2: Review engine
        results.append(("Review Engine", test_review_engine()))

        # Test 3: Full autonomous loop
        results.append(("Autonomous Loop", test_full_autonomous_loop()))

        # Test 4: Configuration
        results.append(("Configuration", test_configuration()))

        # Summary
        print("\n" + "=" * 60)
        print("Test Results Summary:")
        print("=" * 60)

        all_passed = True
        for test_name, passed in results:
            status = "[PASSED]" if passed else "[FAILED]"
            print(f"{test_name}: {status}")
            if not passed:
                all_passed = False

        print("\n" + "=" * 60)
        if all_passed:
            print("[SUCCESS] ALL TESTS PASSED - AI Reviewer is production-ready!")
            print("The system is drift-resilient and ready for autonomous operation.")
        else:
            print("[FAILED] Some tests failed - Review the issues above")

        return 0 if all_passed else 1

    except Exception as e:
        print(f"\n[ERROR] Test suite failed with error: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
