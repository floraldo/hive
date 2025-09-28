#!/usr/bin/env python3
"""
Comprehensive test suite for Hive V2.0 Windows integration.
Consolidates all test scenarios into a single, organized test runner.
"""

import sys
import os
import json
import sqlite3
import subprocess
import time
import tempfile
from pathlib import Path
from datetime import datetime, timezone
import uuid

# No sys.path manipulation needed - use Poetry workspace imports
project_root = Path(__file__).parent.parent.parent.parent
# All packages available through Poetry workspace imports

from hive_orchestrator.hive_core import HiveCore
import hive_core_db
from hive_utils.paths import DB_PATH


class HiveTestSuite:
    """Comprehensive test suite for Hive V2.0"""

    def __init__(self):
        self.results = []
        self.hive = None

    def log(self, message: str):
        """Log test message"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {message}")

    def setup(self):
        """Set up test environment"""
        self.log("Setting up test environment...")

        # Initialize HiveCore
        self.hive = HiveCore()

        # Clean up test tasks
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM tasks WHERE id LIKE 'test-%'")
        conn.commit()
        conn.close()

        self.log("Test environment ready")

    def create_test_task(self, task_id: str, worker: str = "backend") -> dict:
        """Create a test task in the database"""
        task_data = {
            "id": task_id,
            "title": "Test Task",
            "description": f"Test task for {worker}",
            "task_type": "simple",
            "priority": 1,
            "status": "queued",
            "payload": json.dumps({
                "message": f"Test message for {worker}",
                "action": "test"
            }),
            "assigned_worker": worker,
            "workspace_type": "repo",
            "created_at": datetime.now(timezone.utc).isoformat()
        }

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO tasks (
                id, title, description, task_type, priority, status,
                payload, assigned_worker, workspace_type, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            task_data["id"],
            task_data["title"],
            task_data["description"],
            task_data["task_type"],
            task_data["priority"],
            task_data["status"],
            task_data["payload"],
            task_data["assigned_worker"],
            task_data["workspace_type"],
            task_data["created_at"]
        ))
        conn.commit()
        conn.close()

        return task_data

    def test_worker_spawning(self) -> bool:
        """Test direct worker spawning using module approach"""
        self.log("Testing direct worker spawning...")

        # Create test task
        task_id = f"test-spawn-{uuid.uuid4().hex[:8]}"
        self.create_test_task(task_id)

        # Build command using module approach
        cmd = [
            sys.executable,
            "-m", "hive_orchestrator.worker",
            "backend",
            "--one-shot",
            "--task-id", task_id,
            "--run-id", f"test-{uuid.uuid4().hex[:8]}",
            "--phase", "apply",
            "--mode", "repo"
        ]

        # Set up environment
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        orchestrator_src = (self.hive.root / "apps" / "hive-orchestrator" / "src").as_posix()
        env["PYTHONPATH"] = orchestrator_src

        try:
            # Spawn worker with timeout
            process = subprocess.Popen(
                cmd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env
            )

            # Give it 3 seconds to initialize
            time.sleep(3)

            # Check if process is running
            if process.poll() is None:
                self.log("Worker spawned successfully and is running")
                # Terminate cleanly
                process.terminate()
                time.sleep(1)
                if process.poll() is None:
                    process.kill()
                return True
            else:
                stdout, stderr = process.communicate()
                self.log(f"Worker exited early with code {process.returncode}")
                if stderr:
                    self.log(f"Error: {stderr[:300]}")
                return False

        except Exception as e:
            self.log(f"Failed to spawn worker: {e}")
            return False

    def test_error_handling(self) -> bool:
        """Test error capture for invalid tasks"""
        self.log("Testing error handling...")

        cmd = [
            sys.executable,
            "-m", "hive_orchestrator.worker",
            "backend",
            "--one-shot",
            "--task-id", "invalid-task-id",
            "--run-id", "test-error",
            "--phase", "apply",
            "--mode", "repo"
        ]

        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        orchestrator_src = (self.hive.root / "apps" / "hive-orchestrator" / "src").as_posix()
        env["PYTHONPATH"] = orchestrator_src

        try:
            process = subprocess.run(
                cmd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env,
                timeout=10
            )

            # Should exit with code 2 for task not found
            if process.returncode == 2 and "Task not found" in process.stderr:
                self.log("Error handling working correctly")
                return True
            else:
                self.log(f"Unexpected behavior: code={process.returncode}, stderr={process.stderr[:200]}")
                return False

        except subprocess.TimeoutExpired:
            self.log("Error test timed out unexpectedly")
            return False
        except Exception as e:
            self.log(f"Error test failed: {e}")
            return False

    def test_configuration(self) -> bool:
        """Test configuration loading"""
        self.log("Testing configuration...")

        try:
            from hive_orchestrator.config import get_config

            config = get_config()

            # Check essential config values
            required_keys = [
                "worker_spawn_timeout",
                "status_refresh_seconds",
                "max_parallel_tasks"
            ]

            for key in required_keys:
                if config.get(key) is None:
                    self.log(f"Missing config key: {key}")
                    return False

            self.log("Configuration loaded successfully")
            return True

        except Exception as e:
            self.log(f"Configuration test failed: {e}")
            return False

    def test_queen_runner(self) -> bool:
        """Test Queen runner script"""
        self.log("Testing Queen runner...")

        queen_script = Path(__file__).parent.parent / "run_queen.py"

        if not queen_script.exists():
            self.log("Queen runner script not found")
            return False

        try:
            # Test help command
            result = subprocess.run(
                [sys.executable, str(queen_script), "--help"],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0 and "QueenLite" in result.stdout:
                self.log("Queen runner script working")
                return True
            else:
                self.log(f"Queen runner test failed: {result.stderr}")
                return False

        except Exception as e:
            self.log(f"Queen runner test error: {e}")
            return False

    def test_database_integration(self) -> bool:
        """Test database operations"""
        self.log("Testing database integration...")

        try:
            # Test task creation and retrieval
            task_id = f"test-db-{uuid.uuid4().hex[:8]}"
            self.create_test_task(task_id)

            # Retrieve task
            task = hive_core_db.get_task(task_id)

            if task and task.get("id") == task_id:
                self.log("Database integration working")
                return True
            else:
                self.log("Failed to retrieve created task")
                return False

        except Exception as e:
            self.log(f"Database test failed: {e}")
            return False

    def run_test(self, test_name: str, test_func) -> bool:
        """Run a single test and record result"""
        self.log(f"Running {test_name}...")
        try:
            result = test_func()
            status = "PASSED" if result else "FAILED"
            self.log(f"{test_name}: {status}")
            self.results.append((test_name, result))
            return result
        except Exception as e:
            self.log(f"{test_name}: FAILED ({e})")
            self.results.append((test_name, False))
            return False

    def run_all_tests(self):
        """Run all tests"""
        self.log("=" * 70)
        self.log("Hive V2.0 Comprehensive Test Suite")
        self.log("=" * 70)

        # Setup
        self.setup()

        # Run tests
        tests = [
            ("Configuration Loading", self.test_configuration),
            ("Database Integration", self.test_database_integration),
            ("Worker Spawning", self.test_worker_spawning),
            ("Error Handling", self.test_error_handling),
            ("Queen Runner", self.test_queen_runner)
        ]

        for test_name, test_func in tests:
            self.run_test(test_name, test_func)

        # Summary
        self.print_summary()

    def print_summary(self):
        """Print test results summary"""
        self.log("=" * 70)
        self.log("TEST RESULTS SUMMARY")
        self.log("=" * 70)

        passed = sum(1 for _, result in self.results if result)
        total = len(self.results)

        for test_name, result in self.results:
            status = "PASSED" if result else "FAILED"
            self.log(f"{test_name}: {status}")

        self.log("=" * 70)
        self.log(f"Results: {passed}/{total} tests passed")

        if passed == total:
            self.log("ALL TESTS PASSED! Windows integration is working correctly.")
            return 0
        else:
            self.log("Some tests failed. Please review the output above.")
            return 1


def main():
    """Run comprehensive test suite"""
    suite = HiveTestSuite()
    return suite.run_all_tests()


if __name__ == "__main__":
    sys.exit(main())