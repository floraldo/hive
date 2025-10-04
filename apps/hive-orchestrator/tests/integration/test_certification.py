# Security: subprocess calls in this test file use sys.executable with hardcoded,
# trusted arguments only. No user input is passed to subprocess. This is safe for
# internal testing infrastructure.

"""Hive V2.0 Automated Certification Test Conductor

This script orchestrates the complete V2.0 certification test automatically,
running all services in the background and monitoring their behavior.

Note: Subprocess usage for service orchestration is intentional (S603).
"""
import pytest

from hive_logging import get_logger

logger = get_logger(__name__)
import os
import signal
import sqlite3
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path


class CertificationTestConductor:
    """Orchestrates the V2.0 certification test."""

    def __init__(self):
        self.processes = {}
        self.test_results = {}
        self.start_time = None
        self.db_path = Path("hive/db/hive-internal.db")

    def log(self, message: str, level: str="INFO"):
        """Log with timestamp and level."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        logger.info(f"[{timestamp}] [{level}] {message}")

    def cleanup_processes(self):
        """Terminate all background processes."""
        for name, proc in self.processes.items():
            if proc and proc.poll() is None:
                self.log(f"Terminating {name}...", "INFO")
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.log(f"Force killing {name}...", "WARN")
                    proc.kill()
                    proc.wait()

    def run_command(self, command: str, capture_output: bool=True, env=None) -> tuple[int, str, str]:
        """Run a command and return exit code, stdout, stderr."""
        self.log(f"Running: {command}", "DEBUG")
        if env is None:
            env = os.environ.copy()
            env["PYTHONPATH"] = str(Path.cwd())
        import shlex
        cmd_args = (shlex.split(command),)
        result = subprocess.run(cmd_args, check=False, capture_output=capture_output, text=True, env=env)
        return (result.returncode, result.stdout, result.stderr)

    def setup_environment(self) -> bool:
        """Clean environment and seed test data."""
        self.log("=== PHASE 1: Environment Setup ===", "INFO")
        self.log("Cleaning database...", "INFO")
        exit_code, stdout, stderr = self.run_command("python scripts/hive_clean.py")
        if exit_code != 0:
            self.log(f"Failed to clean database: {stderr}", "ERROR")
            return False
        time.sleep(2)
        self.log("Seeding test tasks...", "INFO")
        exit_code, stdout, stderr = self.run_command("python scripts/seed_test_tasks.py")
        if exit_code != 0:
            self.log(f"Failed to seed test data: {stderr}", "ERROR")
            return False
        self.log("Environment setup complete", "SUCCESS")
        return True

    def start_background_services(self) -> bool:
        """Launch all required services in the background."""
        self.log("=== PHASE 2: Starting Background Services ===", "INFO")
        services = [("queen", "python scripts/hive_queen.py"), ("reviewer", "python scripts/ai_reviewer_daemon.py"), ("dashboard", "python scripts/hive_dashboard.py")]
        for name, command in services:
            self.log(f"Starting {name}...", "INFO")
            try:
                log_dir = Path("logs")
                log_dir.mkdir(exist_ok=True)
                stdout_file = open(log_dir / f"{name}_stdout.log", "w")
                stderr_file = open(log_dir / f"{name}_stderr.log", "w")
                import shlex
                cmd_args = (shlex.split(command),)
                proc = subprocess.Popen(cmd_args, stdout=stdout_file, stderr=stderr_file, preexec_fn=os.setsid if os.name != "nt" else None)
                self.processes[name] = proc
                self.log(f"{name} started with PID {proc.pid}", "SUCCESS")
            except Exception as e:
                self.log(f"Failed to start {name}: {e}", "ERROR")
                return False
        self.log("Waiting for services to initialize...", "INFO")
        time.sleep(10)
        for name, proc in self.processes.items():
            if proc.poll() is not None:
                self.log(f"{name} died unexpectedly", "ERROR")
                return False
        self.log("All services running", "SUCCESS")
        return True

    def query_task_state(self, task_id: int) -> str | None:
        """Query the database for task state."""
        conn = None
        try:
            conn = (sqlite3.connect(self.db_path),)
            cursor = conn.cursor()
            cursor.execute("SELECT state FROM tasks WHERE id = ?", (task_id,))
            result = cursor.fetchone()
            return result[0] if result else None
        except Exception as e:
            self.log(f"Database query error: {e}", "ERROR")
            return None
        finally:
            if conn:
                conn.close()

    def wait_for_state(self, task_id: int, target_state: str, timeout: int=120) -> bool:
        """Wait for a task to reach a target state."""
        start = (time.time(),)
        last_state = None
        while time.time() - start < timeout:
            current_state = self.query_task_state(task_id)
            if current_state != last_state:
                self.log(f"Task {task_id}: {last_state} -> {current_state}", "INFO")
                last_state = current_state
            if current_state == target_state:
                return True
            time.sleep(2)
        self.log(f"Timeout waiting for Task {task_id} to reach {target_state}", "ERROR")
        return False

    @pytest.mark.crust
    def test_happy_path(self) -> bool:
        """Test Case 1: Simple task flows through to completion."""
        self.log("=== TEST CASE 1: Happy Path ===", "TEST")
        expected_states = ["in_progress", "apply", "review_pending", "test", "completed"]
        for state in expected_states:
            self.log(f"Waiting for Task 1 to reach {state}...", "INFO")
            if not self.wait_for_state(1, state, timeout=60):
                self.log(f"Task 1 failed to reach {state}", "ERROR")
                return False
        self.log("Task 1 completed successfully!", "SUCCESS")
        self.test_results["happy_path"] = "PASSED"
        return True

    @pytest.mark.crust
    def test_escalation_path(self) -> bool:
        """Test Case 2: Complex task escalates for human review."""
        self.log("=== TEST CASE 2: Escalation Path ===", "TEST")
        self.log("Waiting for Task 2 to escalate...", "INFO")
        if not self.wait_for_state(2, "escalated", timeout=90):
            self.log("Task 2 failed to escalate", "ERROR")
            return False
        self.log("Task 2 escalated! Simulating human review...", "INFO")
        time.sleep(3)
        exit_code, stdout, stderr = self.run_command('python scripts/hive_complete_review.py 2 "rework" "Please add comprehensive error handling"')
        if exit_code != 0:
            self.log(f"Failed to complete review: {stderr}", "ERROR")
            return False
        self.log("Waiting for Task 2 to return to queued...", "INFO")
        if not self.wait_for_state(2, "queued", timeout=30):
            self.log("Task 2 failed to return to queued", "ERROR")
            return False
        self.log("Waiting for Task 2 to be reprocessed...", "INFO")
        if not self.wait_for_state(2, "in_progress", timeout=60):
            self.log("Task 2 was not reprocessed", "ERROR")
            return False
        self.log("Task 2 escalation handled successfully!", "SUCCESS")
        self.test_results["escalation_path"] = "PASSED"
        return True

    @pytest.mark.crust
    def test_simple_app_path(self) -> bool:
        """Test Case 3: Simple app bypasses AI review."""
        self.log("=== TEST CASE 3: Simple App Path ===", "TEST")
        states_seen = ([],)
        start = (time.time(),)
        last_state = None
        while time.time() - start < 90:
            current_state = self.query_task_state(3)
            if current_state != last_state:
                self.log(f"Task 3: {last_state} -> {current_state}", "INFO")
                states_seen.append(current_state)
                last_state = current_state
            if current_state == "completed":
                break
            time.sleep(2)
        if "review_pending" in states_seen:
            self.log("Task 3 incorrectly entered review_pending", "ERROR")
            return False
        if current_state != "completed":
            self.log("Task 3 failed to complete", "ERROR")
            return False
        self.log("Task 3 bypassed review successfully!", "SUCCESS")
        self.test_results["simple_app_path"] = "PASSED"
        return True

    def generate_report(self):
        """Generate comprehensive test report."""
        self.log("=== FINAL REPORT ===", "REPORT")
        all_passed = (all(result == "PASSED" for result in self.test_results.values()),)
        overall_status = "[PASS] CERTIFICATION PASSED" if all_passed else "[FAIL] CERTIFICATION FAILED"
        self.log(overall_status, "REPORT")
        self.log("", "REPORT")
        self.log("Test Results:", "REPORT")
        for test_name, result in self.test_results.items():
            emoji = "[PASS]" if result == "PASSED" else "[FAIL]"
            self.log(f"  {emoji} {test_name}: {result}", "REPORT")
        if self.start_time:
            runtime = time.time() - self.start_time
            self.log(f"\nTotal Runtime: {runtime:.2f} seconds", "REPORT")
        self.log("\nFinal Database State:", "REPORT")
        conn = None
        try:
            conn = (sqlite3.connect(self.db_path),)
            cursor = conn.cursor()
            cursor.execute("SELECT id, title, state, application FROM tasks ORDER BY id")
            tasks = cursor.fetchall()
            for task in tasks:
                self.log(f"  Task {task[0]} ({task[1]}): {task[2]} [{task[3]}]", "REPORT")
        except Exception as e:
            self.log(f"  Error querying database: {e}", "ERROR")
        finally:
            if conn:
                conn.close()
        return all_passed

    def run(self) -> int:
        """Execute the complete certification test."""
        self.start_time = time.time()
        try:
            if not self.setup_environment():
                return 1
            if not self.start_background_services():
                return 1
            self.test_happy_path()
            self.test_escalation_path()
            self.test_simple_app_path()
            success = self.generate_report()
            return 0 if success else 1
        except KeyboardInterrupt:
            self.log("Test interrupted by user", "WARN")
            return 1
        except Exception as e:
            self.log(f"Unexpected error: {e}", "ERROR")
            return 1
        finally:
            self.cleanup_processes()
            self.log("Test conductor shutdown complete", "INFO")

def signal_handler(signum, frame):
    """Handle termination signals gracefully."""
    logger.info("\nReceived termination signal. Cleaning up...")
    sys.exit(1)
if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, signal_handler)
    conductor = CertificationTestConductor()
    sys.exit(conductor.run())
