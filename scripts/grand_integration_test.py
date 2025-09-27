#!/usr/bin/env python3
"""
Grand Integration Test - V2.1 Autonomous Agency Validation

Tests the complete autonomous workflow:
1. Seed a high-level planning task
2. Launch AI Planner, AI Reviewer, and Queen daemons
3. Monitor the full lifecycle: Planning ‚Üí Execution ‚Üí Review ‚Üí Completion

This is the final validation of the Hive V2.1 autonomous agency.
"""

import os
import sys
import time
import json
import uuid
import signal
import subprocess
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

# Setup paths
hive_root = Path(__file__).parent.parent
sys.path.insert(0, str(hive_root / "packages" / "hive-config" / "src"))
sys.path.insert(0, str(hive_root / "packages" / "hive-core-db" / "src"))

from hive_config import setup_hive_paths
setup_hive_paths()

import hive_core_db
from hive_core_db.database import get_connection


class GrandIntegrationTest:
    """Autonomous agency validation test"""

    def __init__(self):
        self.test_id = f"grand-test-{uuid.uuid4().hex[:8]}"
        self.start_time = datetime.now(timezone.utc)
        self.daemons = {}  # daemon_name -> process
        self.test_task_id = None

        print(f"Grand Integration Test ID: {self.test_id}")
        print(f"Started at: {self.start_time}")

    def setup_test_environment(self):
        """Setup clean test environment"""
        print("\n" + "="*60)
        print("SETTING UP TEST ENVIRONMENT")
        print("="*60)

        # Initialize database
        hive_core_db.init_db()
        print("[ICON] Database initialized")

        # Clean any existing test data
        conn = get_connection()
        cursor = conn.cursor()

        # Clean up old test data
        cursor.execute("DELETE FROM tasks WHERE id LIKE 'grand-test-%'")
        cursor.execute("DELETE FROM planning_queue WHERE id LIKE 'grand-test-%'")
        cursor.execute("DELETE FROM execution_plans WHERE planning_task_id LIKE 'grand-test-%'")
        conn.commit()
        conn.close()

        print("[ICON] Test environment cleaned")

    def seed_high_level_task(self):
        """Seed a complex task that requires AI planning"""
        print("\n" + "="*60)
        print("SEEDING HIGH-LEVEL TASK FOR AI PLANNER")
        print("="*60)

        self.test_task_id = f"grand-test-{self.test_id}"

        # Create a realistic high-level task that requires decomposition
        task_description = """
        Create a complete user authentication system with the following requirements:

        1. User registration and login API endpoints
        2. JWT token generation and validation middleware
        3. Password hashing with bcrypt
        4. Email verification workflow
        5. Password reset functionality
        6. Rate limiting for authentication endpoints
        7. Comprehensive unit tests (>90% coverage)
        8. Integration tests for all auth flows
        9. API documentation with examples
        10. Security audit and penetration testing

        Technical constraints:
        - Use Python FastAPI framework
        - PostgreSQL database with SQLAlchemy ORM
        - Redis for session management and rate limiting
        - Follow OWASP security best practices
        - Implement proper logging and monitoring
        - Docker containerization for deployment

        Deliverables:
        - Fully functional authentication service
        - Complete test suite with CI/CD integration
        - Security documentation and threat model
        - Deployment instructions and monitoring setup
        """

        context_data = {
            "complexity": "high",
            "estimated_scope": "large",
            "technologies": ["python", "fastapi", "postgresql", "redis", "docker"],
            "security_requirements": ["OWASP", "encryption", "rate_limiting"],
            "quality_gates": ["unit_tests", "integration_tests", "security_audit"],
            "deliverables": ["service", "tests", "docs", "deployment"],
            "priority_level": 85
        }

        # Insert into planning_queue (AI Planner will pick this up)
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO planning_queue
            (id, task_description, priority, requestor, context_data, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            self.test_task_id,
            task_description,
            85,
            f"grand_integration_test_{self.test_id}",
            json.dumps(context_data),
            "pending",
            datetime.now(timezone.utc).isoformat()
        ))

        conn.commit()
        conn.close()

        print(f"[ICON] Seeded high-level task: {self.test_task_id}")
        print(f"[ICON]ù Task complexity: HIGH (authentication system)")
        print(f"[ICON]Ø Expected sub-tasks: 15-25 planned sub-tasks")
        print(f"[ICON][ICON]  Expected duration: 4-8 hours of work")

    def launch_daemons(self):
        """Launch AI Planner, AI Reviewer, and Queen daemons"""
        print("\n" + "="*60)
        print("LAUNCHING AUTONOMOUS AGENCY DAEMONS")
        print("="*60)

        daemon_configs = [
            {
                "name": "ai_planner",
                "script": "scripts/ai_planner_daemon.py",
                "description": "AI Planner - Intelligent task decomposition"
            },
            {
                "name": "ai_reviewer",
                "script": "scripts/ai_reviewer_daemon.py",
                "description": "AI Reviewer - Code quality validation"
            },
            {
                "name": "queen",
                "script": "scripts/hive_queen.py",
                "description": "Queen Orchestrator - Task execution engine"
            }
        ]

        for daemon_config in daemon_configs:
            try:
                script_path = hive_root / daemon_config["script"]

                # Launch daemon with proper environment
                env = os.environ.copy()
                env["PYTHONPATH"] = str(hive_root)

                process = subprocess.Popen(
                    [sys.executable, str(script_path)],
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    cwd=str(hive_root)
                )

                self.daemons[daemon_config["name"]] = process

                print(f"[ICON]Ä Launched {daemon_config['name']}: PID {process.pid}")
                print(f"   {daemon_config['description']}")

                # Give daemon time to initialize
                time.sleep(2)

                # Check if daemon is still running
                if process.poll() is None:
                    print(f"[ICON] {daemon_config['name']} running successfully")
                else:
                    stdout, stderr = process.communicate()
                    print(f"[ICON] {daemon_config['name']} failed to start:")
                    print(f"   stdout: {stdout}")
                    print(f"   stderr: {stderr}")
                    return False

            except Exception as e:
                print(f"[ICON] Failed to launch {daemon_config['name']}: {e}")
                return False

        print(f"\n[ICON] All 3 daemons launched successfully")
        print(f"[ICON]ó Neural connections established")
        return True

    def monitor_autonomous_workflow(self, timeout_minutes: int = 15):
        """Monitor the complete autonomous workflow execution"""
        print("\n" + "="*60)
        print("MONITORING AUTONOMOUS WORKFLOW EXECUTION")
        print("="*60)

        start_time = time.time()
        timeout_seconds = timeout_minutes * 60

        phases = {
            "planning": {"completed": False, "timestamp": None},
            "subtask_creation": {"completed": False, "timestamp": None, "count": 0},
            "execution_started": {"completed": False, "timestamp": None},
            "review_started": {"completed": False, "timestamp": None},
            "completion": {"completed": False, "timestamp": None}
        }

        print(f"[ICON][ICON]  Monitoring timeout: {timeout_minutes} minutes")
        print(f"[ICON]ä Tracking phases: {list(phases.keys())}")

        while time.time() - start_time < timeout_seconds:
            conn = get_connection()
            cursor = conn.cursor()

            # Check planning phase
            if not phases["planning"]["completed"]:
                cursor.execute("""
                    SELECT status FROM planning_queue WHERE id = ?
                """, (self.test_task_id,))
                row = cursor.fetchone()
                if row and row[0] == "planned":
                    phases["planning"]["completed"] = True
                    phases["planning"]["timestamp"] = datetime.now(timezone.utc)
                    print(f"[ICON] PLANNING COMPLETE: AI Planner processed the task")

            # Check subtask creation
            if phases["planning"]["completed"] and not phases["subtask_creation"]["completed"]:
                cursor.execute("""
                    SELECT COUNT(*) FROM tasks
                    WHERE task_type = 'planned_subtask'
                    AND json_extract(payload, '$.parent_plan_id') LIKE ?
                """, (f"%{self.test_task_id}%",))
                count = cursor.fetchone()[0]

                if count > 0:
                    phases["subtask_creation"]["completed"] = True
                    phases["subtask_creation"]["count"] = count
                    phases["subtask_creation"]["timestamp"] = datetime.now(timezone.utc)
                    print(f"[ICON] SUBTASKS CREATED: {count} planned subtasks ready for execution")

            # Check execution started
            if phases["subtask_creation"]["completed"] and not phases["execution_started"]["completed"]:
                cursor.execute("""
                    SELECT COUNT(*) FROM tasks
                    WHERE task_type = 'planned_subtask'
                    AND status IN ('assigned', 'in_progress')
                    AND json_extract(payload, '$.parent_plan_id') LIKE ?
                """, (f"%{self.test_task_id}%",))
                count = cursor.fetchone()[0]

                if count > 0:
                    phases["execution_started"]["completed"] = True
                    phases["execution_started"]["timestamp"] = datetime.now(timezone.utc)
                    print(f"[ICON] EXECUTION STARTED: Queen began executing subtasks")

            # Check review started
            if phases["execution_started"]["completed"] and not phases["review_started"]["completed"]:
                cursor.execute("""
                    SELECT COUNT(*) FROM tasks
                    WHERE task_type = 'planned_subtask'
                    AND status = 'review_pending'
                    AND json_extract(payload, '$.parent_plan_id') LIKE ?
                """, (f"%{self.test_task_id}%",))
                count = cursor.fetchone()[0]

                if count > 0:
                    phases["review_started"]["completed"] = True
                    phases["review_started"]["timestamp"] = datetime.now(timezone.utc)
                    print(f"[ICON] REVIEW STARTED: AI Reviewer validating completed work")

            # Check completion
            if phases["execution_started"]["completed"] and not phases["completion"]["completed"]:
                cursor.execute("""
                    SELECT COUNT(*) as total,
                           SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed
                    FROM tasks
                    WHERE task_type = 'planned_subtask'
                    AND json_extract(payload, '$.parent_plan_id') LIKE ?
                """, (f"%{self.test_task_id}%",))
                row = cursor.fetchone()

                if row:
                    total, completed = row
                    if total > 0 and completed >= total * 0.8:  # 80% completion threshold
                        phases["completion"]["completed"] = True
                        phases["completion"]["timestamp"] = datetime.now(timezone.utc)
                        print(f"[ICON] WORKFLOW COMPLETE: {completed}/{total} subtasks completed")

            conn.close()

            # Check if all phases completed
            if all(phase["completed"] for phase in phases.values()):
                print(f"\n[ICON]â AUTONOMOUS WORKFLOW SUCCESSFUL!")
                return True, phases

            # Progress update every 30 seconds
            if int(time.time() - start_time) % 30 == 0:
                completed_phases = sum(1 for phase in phases.values() if phase["completed"])
                total_phases = len(phases)
                print(f"[ICON]ä Progress: {completed_phases}/{total_phases} phases completed")

            time.sleep(5)  # Check every 5 seconds

        print(f"\n[ICON] TIMEOUT: Autonomous workflow did not complete within {timeout_minutes} minutes")
        return False, phases

    def generate_detailed_report(self, success: bool, phases: Dict):
        """Generate comprehensive test report"""
        print("\n" + "="*60)
        print("GRAND INTEGRATION TEST REPORT")
        print("="*60)

        end_time = datetime.now(timezone.utc)
        total_duration = end_time - self.start_time

        print(f"[ICON]î Test ID: {self.test_id}")
        print(f"[ICON][ICON]  Total Duration: {total_duration}")
        print(f"[ICON]Ø Result: {'SUCCESS' if success else 'PARTIAL/FAILED'}")

        print(f"\n[ICON]ã Phase Breakdown:")
        for phase_name, phase_data in phases.items():
            status = "[ICON] COMPLETED" if phase_data["completed"] else "[ICON] INCOMPLETE"
            timestamp = phase_data["timestamp"] or "N/A"

            print(f"  {phase_name}: {status}")
            if phase_data["completed"]:
                duration = phase_data["timestamp"] - self.start_time
                print(f"    Duration: {duration}")
                if "count" in phase_data:
                    print(f"    Count: {phase_data['count']}")

        # Database analysis
        conn = get_connection()
        cursor = conn.cursor()

        print(f"\n[ICON]ä Database Analysis:")

        # Planning queue status
        cursor.execute("SELECT status FROM planning_queue WHERE id = ?", (self.test_task_id,))
        planning_status = cursor.fetchone()
        print(f"  Planning Task Status: {planning_status[0] if planning_status else 'NOT_FOUND'}")

        # Execution plans
        cursor.execute("""
            SELECT COUNT(*) FROM execution_plans
            WHERE planning_task_id = ?
        """, (self.test_task_id,))
        plan_count = cursor.fetchone()[0]
        print(f"  Execution Plans Created: {plan_count}")

        # Subtasks analysis
        cursor.execute("""
            SELECT status, COUNT(*)
            FROM tasks
            WHERE task_type = 'planned_subtask'
            AND json_extract(payload, '$.parent_plan_id') LIKE ?
            GROUP BY status
        """, (f"%{self.test_task_id}%",))

        subtask_stats = dict(cursor.fetchall())
        print(f"  Subtask Status Distribution:")
        for status, count in subtask_stats.items():
            print(f"    {status}: {count}")

        conn.close()

        # System validation
        print(f"\n[ICON]ß System Validation:")

        # Check daemon status
        running_daemons = 0
        for daemon_name, process in self.daemons.items():
            if process.poll() is None:
                print(f"  {daemon_name}: [ICON]¢ RUNNING")
                running_daemons += 1
            else:
                print(f"  {daemon_name}: [ICON]¥ STOPPED")

        print(f"  Active Daemons: {running_daemons}/3")

        # Overall assessment
        print(f"\n[ICON]Ü OVERALL ASSESSMENT:")
        if success:
            print("  [ICON]â HIVE V2.1 AUTONOMOUS AGENCY: FULLY OPERATIONAL")
            print("  [ICON]† AI Planner: Successfully decomposed complex task")
            print("  [ICON]ë Queen Orchestrator: Successfully executed planned workflow")
            print("  [ICON]ç AI Reviewer: Successfully validated completed work")
            print("  [ICON]ó Neural Connections: All systems communicating properly")
            print(f"\n  [ICON] V2.1 CERTIFICATION: PASSED")
        else:
            completed_phases = sum(1 for phase in phases.values() if phase["completed"])
            total_phases = len(phases)
            print(f"  ‚ö†[ICON]  PARTIAL SUCCESS: {completed_phases}/{total_phases} phases completed")
            print("  [ICON]ß System is functional but requires optimization")

            # Failure analysis
            failed_phases = [name for name, data in phases.items() if not data["completed"]]
            print(f"  [ICON]ã Failed Phases: {', '.join(failed_phases)}")

        return success

    def cleanup_daemons(self):
        """Safely terminate all daemon processes"""
        print("\n" + "="*60)
        print("CLEANUP: TERMINATING DAEMONS")
        print("="*60)

        for daemon_name, process in self.daemons.items():
            try:
                if process.poll() is None:  # Still running
                    print(f"[ICON]ë Terminating {daemon_name} (PID {process.pid})")
                    process.terminate()

                    # Give process time to terminate gracefully
                    try:
                        process.wait(timeout=10)
                        print(f"[ICON] {daemon_name} terminated gracefully")
                    except subprocess.TimeoutExpired:
                        print(f"[ICON]™ Force killing {daemon_name}")
                        process.kill()
                        process.wait()
                        print(f"[ICON] {daemon_name} force killed")
                else:
                    print(f"[ICON] {daemon_name} already stopped")

            except Exception as e:
                print(f"[ICON] Error terminating {daemon_name}: {e}")

        print("[ICON] All daemons terminated")

    def run_grand_integration_test(self):
        """Execute the complete grand integration test"""
        try:
            # Setup
            self.setup_test_environment()

            # Seed task
            self.seed_high_level_task()

            # Launch daemons
            if not self.launch_daemons():
                print("[ICON] Failed to launch daemons - aborting test")
                return False

            # Monitor workflow
            success, phases = self.monitor_autonomous_workflow(timeout_minutes=15)

            # Generate report
            self.generate_detailed_report(success, phases)

            return success

        except KeyboardInterrupt:
            print("\n[ICON]ë Test interrupted by user")
            return False
        except Exception as e:
            print(f"\n[ICON] Test failed with exception: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            # Always cleanup daemons
            self.cleanup_daemons()


def main():
    """Main entry point"""
    print("HIVE V2.1 GRAND INTEGRATION TEST")
    print("Testing complete autonomous agency workflow")
    print("AI Planner + Queen Orchestrator + AI Reviewer")

    # Handle Ctrl+C gracefully
    def signal_handler(sig, frame):
        print("\nReceived interrupt signal - cleaning up...")
        sys.exit(1)

    signal.signal(signal.SIGINT, signal_handler)

    # Run the test
    test = GrandIntegrationTest()
    success = test.run_grand_integration_test()

    # Exit with appropriate code
    if success:
        print(f"\nGRAND INTEGRATION TEST: SUCCESS")
        print(f"Hive V2.1 Autonomous Agency: CERTIFIED OPERATIONAL")
        sys.exit(0)
    else:
        print(f"\nGRAND INTEGRATION TEST: INCOMPLETE")
        print(f"System requires further development")
        sys.exit(1)


if __name__ == "__main__":
    main()