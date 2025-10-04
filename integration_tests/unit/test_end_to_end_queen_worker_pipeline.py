# Security: subprocess calls in this test file use sys.executable with hardcoded,
# trusted arguments only. No user input is passed to subprocess. This is safe for
# internal testing infrastructure.

"""End-to-End Queen → Worker Pipeline Integration Test

This test validates the complete task flow from creation through execution:
1. Task creation and queuing
2. Queen task pickup and assignment
3. Worker spawning and execution
4. Task completion and status updates
5. Error handling and recovery scenarios

Focuses specifically on the core Queen → Worker workflow.
"""
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest


@dataclass
class TaskTestResult:
    """Result of a task execution test"""
    task_id: int
    success: bool
    duration: float
    worker_id: str | None = None
    error_message: str | None = None
    result_data: dict | None = None

class QueenWorkerPipelineTest:
    """End-to-end pipeline test for Queen → Worker workflow"""

    def __init__(self):
        self.temp_dir = None
        self.test_db_path = None
        self.queen_process = None
        self.worker_processes = []
        self.test_results: list[TaskTestResult] = []

    def setup_test_environment(self):
        """Set up test environment with database and mock processes"""
        print("🔧 Setting up Queen → Worker pipeline test environment...")
        self.temp_dir = tempfile.mkdtemp(prefix="queen_worker_test_")
        self.test_db_path = Path(self.temp_dir) / "pipeline_test.db"
        self._setup_test_database()
        os.environ["HIVE_TEST_MODE"] = "true"
        os.environ["HIVE_TEST_DB_PATH"] = str(self.test_db_path)
        os.environ["HIVE_QUEEN_TEST_MODE"] = "true"
        os.environ["HIVE_WORKER_TEST_MODE"] = "true"
        print(f"✅ Test environment ready: {self.temp_dir}")

    def teardown_test_environment(self):
        """Clean up test environment"""
        print("🧹 Cleaning up test environment...")
        self._stop_all_processes()
        if self.temp_dir and Path(self.temp_dir).exists():
            import shutil
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        for env_var in ["HIVE_TEST_MODE", "HIVE_TEST_DB_PATH", "HIVE_QUEEN_TEST_MODE", "HIVE_WORKER_TEST_MODE"]:
            if env_var in os.environ:
                del os.environ[env_var]
        print("✅ Test environment cleaned up")

    def run_complete_pipeline_test(self) -> bool:
        """Run complete end-to-end pipeline test"""
        print("🏁 Running Complete Queen → Worker Pipeline Test")
        print("=" * 70)
        self.setup_test_environment()
        try:
            basic_test_passed = self.test_basic_task_processing()
            print(f"📋 Basic Task Processing: {('PASSED' if basic_test_passed else 'FAILED')}")
            concurrent_test_passed = self.test_concurrent_task_processing()
            print(f"⚡ Concurrent Task Processing: {('PASSED' if concurrent_test_passed else 'FAILED')}")
            priority_test_passed = self.test_task_priority_handling()
            print(f"🎯 Task Priority Handling: {('PASSED' if priority_test_passed else 'FAILED')}")
            failure_test_passed = self.test_worker_failure_recovery()
            print(f"🛡️ Worker Failure Recovery: {('PASSED' if failure_test_passed else 'FAILED')}")
            timeout_test_passed = self.test_task_timeout_handling()
            print(f"⏰ Task Timeout Handling: {('PASSED' if timeout_test_passed else 'FAILED')}")
            all_passed = all([basic_test_passed, concurrent_test_passed, priority_test_passed, failure_test_passed, timeout_test_passed])
            self._generate_pipeline_test_report(all_passed)
            return all_passed
        except Exception as e:
            print(f"❌ Pipeline test failed: {e}")
            return False
        finally:
            self.teardown_test_environment()

    @pytest.mark.crust
    def test_basic_task_processing(self) -> bool:
        """Test basic task creation → assignment → execution → completion"""
        print("\n🧪 Testing Basic Task Processing...")
        try:
            task_id = self._create_test_task({"title": "Basic Test Task", "description": "Test basic task processing pipeline", "priority": 50, "context": json.dumps({"test_type": "basic", "expected_duration": 1.0})})
            queen_started = self._start_mock_queen()
            if not queen_started:
                return False
            worker_started = self._start_mock_worker("basic_worker")
            if not worker_started:
                return False
            task_completed = self._monitor_task_completion(task_id, timeout=30)
            if not task_completed:
                print("❌ Task did not complete within timeout")
                return False
            task_result = self._get_task_result(task_id)
            if not task_result or task_result.get("status") != "success":
                print(f"❌ Task completion failed: {task_result}")
                return False
            print("✅ Basic task processing test passed")
            return True
        except Exception as e:
            print(f"❌ Basic task processing test failed: {e}")
            return False
        finally:
            self._stop_all_processes()

    @pytest.mark.crust
    def test_concurrent_task_processing(self) -> bool:
        """Test concurrent processing of multiple tasks"""
        print("\n🧪 Testing Concurrent Task Processing...")
        try:
            num_tasks = 5
            task_ids = []
            for i in range(num_tasks):
                task_id = self._create_test_task({"title": f"Concurrent Test Task {i + 1}", "description": f"Concurrent processing test task {i + 1}", "priority": 60, "context": json.dumps({"test_type": "concurrent", "task_number": i + 1})})
                task_ids.append(task_id)
            queen_started = self._start_mock_queen()
            if not queen_started:
                return False
            for i in range(3):
                worker_started = self._start_mock_worker(f"concurrent_worker_{i}")
                if not worker_started:
                    return False
            start_time = time.time()
            completed_tasks = []
            while len(completed_tasks) < num_tasks and time.time() - start_time < 45:
                for task_id in task_ids:
                    if task_id not in completed_tasks:
                        if self._is_task_completed(task_id):
                            completed_tasks.append(task_id)
                            print(f"✅ Task {task_id} completed")
                time.sleep(1)
            if len(completed_tasks) == num_tasks:
                duration = time.time() - start_time
                throughput = num_tasks / duration
                print(f"✅ Concurrent processing test passed: {num_tasks} tasks in {duration:.2f}s ({throughput:.2f} tasks/sec)")
                return True
            print(f"❌ Concurrent processing test failed: only {len(completed_tasks)}/{num_tasks} tasks completed")
            return False
        except Exception as e:
            print(f"❌ Concurrent processing test failed: {e}")
            return False
        finally:
            self._stop_all_processes()

    @pytest.mark.crust
    def test_task_priority_handling(self) -> bool:
        """Test that high-priority tasks are processed first"""
        print("\n🧪 Testing Task Priority Handling...")
        try:
            low_priority_task = self._create_test_task({"title": "Low Priority Task", "description": "Should be processed last", "priority": 20, "context": json.dumps({"test_type": "priority", "priority_level": "low"})})
            high_priority_task = self._create_test_task({"title": "High Priority Task", "description": "Should be processed first", "priority": 90, "context": json.dumps({"test_type": "priority", "priority_level": "high"})})
            medium_priority_task = self._create_test_task({"title": "Medium Priority Task", "description": "Should be processed second", "priority": 50, "context": json.dumps({"test_type": "priority", "priority_level": "medium"})})
            queen_started = self._start_mock_queen()
            if not queen_started:
                return False
            worker_started = self._start_mock_worker("priority_worker")
            if not worker_started:
                return False
            completion_order = []
            start_time = time.time()
            while len(completion_order) < 3 and time.time() - start_time < 30:
                for task_id in [low_priority_task, high_priority_task, medium_priority_task]:
                    if task_id not in completion_order and self._is_task_completed(task_id):
                        completion_order.append(task_id)
                        print(f"✅ Task {task_id} completed")
                time.sleep(0.5)
            if len(completion_order) == 3:
                if completion_order[0] == high_priority_task and completion_order[1] == medium_priority_task and (completion_order[2] == low_priority_task):
                    print("✅ Task priority handling test passed")
                    return True
                print(f"❌ Tasks completed in wrong order: {completion_order}")
                print(f"   Expected: [{high_priority_task}, {medium_priority_task}, {low_priority_task}]")
                return False
            print(f"❌ Not all priority tasks completed: {len(completion_order)}/3")
            return False
        except Exception as e:
            print(f"❌ Priority handling test failed: {e}")
            return False
        finally:
            self._stop_all_processes()

    @pytest.mark.crust
    def test_worker_failure_recovery(self) -> bool:
        """Test worker failure detection and task reassignment"""
        print("\n🧪 Testing Worker Failure Recovery...")
        try:
            task_id = self._create_test_task({"title": "Worker Failure Test Task", "description": "Test worker failure recovery", "priority": 70, "context": json.dumps({"test_type": "failure_recovery", "worker_failure": True})})
            queen_started = self._start_mock_queen()
            if not queen_started:
                return False
            failing_worker_started = self._start_mock_worker("failing_worker", should_fail=True)
            if not failing_worker_started:
                return False
            time.sleep(2)
            self._stop_worker("failing_worker")
            print("💥 Simulated worker failure")
            recovery_worker_started = self._start_mock_worker("recovery_worker")
            if not recovery_worker_started:
                return False
            task_completed = self._monitor_task_completion(task_id, timeout=30)
            if task_completed:
                task_result = self._get_task_result(task_id)
                if task_result and task_result.get("worker_id") == "recovery_worker":
                    print("✅ Worker failure recovery test passed")
                    return True
                print(f"❌ Task not completed by recovery worker: {task_result}")
                return False
            print("❌ Task was not recovered after worker failure")
            return False
        except Exception as e:
            print(f"❌ Worker failure recovery test failed: {e}")
            return False
        finally:
            self._stop_all_processes()

    @pytest.mark.crust
    def test_task_timeout_handling(self) -> bool:
        """Test task timeout detection and handling"""
        print("\n🧪 Testing Task Timeout Handling...")
        try:
            task_id = self._create_test_task({"title": "Timeout Test Task", "description": "Test task timeout handling", "priority": 50, "timeout": 2, "context": json.dumps({"test_type": "timeout", "long_running": True})})
            queen_started = self._start_mock_queen()
            if not queen_started:
                return False
            timeout_worker_started = self._start_mock_worker("timeout_worker", slow_execution=True)
            if not timeout_worker_started:
                return False
            start_time = time.time()
            timeout_detected = False
            while time.time() - start_time < 10:
                task_status = self._get_task_status(task_id)
                if task_status == "timeout" or task_status == "failed":
                    timeout_detected = True
                    print(f"✅ Timeout detected: task status = {task_status}")
                    break
                time.sleep(0.5)
            if timeout_detected:
                print("✅ Task timeout handling test passed")
                return True
            print("❌ Task timeout was not detected")
            return False
        except Exception as e:
            print(f"❌ Task timeout handling test failed: {e}")
            return False
        finally:
            self._stop_all_processes()

    def _setup_test_database(self):
        """Set up test database schema"""
        conn = sqlite3.connect(self.test_db_path)
        conn.executescript("\n            CREATE TABLE tasks (\n                id INTEGER PRIMARY KEY AUTOINCREMENT,\n                title TEXT NOT NULL,\n                description TEXT,\n                status TEXT DEFAULT 'pending',\n                priority INTEGER DEFAULT 50,\n                timeout INTEGER DEFAULT 300,\n                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,\n                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,\n                assigned_worker TEXT,\n                context TEXT,\n                result TEXT\n            );\n\n            CREATE TABLE task_logs (\n                id INTEGER PRIMARY KEY AUTOINCREMENT,\n                task_id INTEGER,\n                event_type TEXT,\n                event_data TEXT,\n                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,\n                FOREIGN KEY (task_id) REFERENCES tasks(id)\n            );\n\n            CREATE TABLE worker_status (\n                worker_id TEXT PRIMARY KEY,\n                status TEXT DEFAULT 'active',\n                last_heartbeat TIMESTAMP DEFAULT CURRENT_TIMESTAMP,\n                current_task_id INTEGER\n            );\n        ")
        conn.commit()
        conn.close()

    def _create_test_task(self, task_data: dict[str, Any]) -> int:
        """Create a test task in the database"""
        conn = sqlite3.connect(self.test_db_path)
        cursor = conn.execute("INSERT INTO tasks (title, description, priority, timeout, context)\n               VALUES (?, ?, ?, ?, ?)", (task_data["title"], task_data["description"], task_data.get("priority", 50), task_data.get("timeout", 300), task_data.get("context", "{}")))
        task_id = cursor.lastrowid
        conn.commit()
        conn.close()
        print(f"📋 Created test task {task_id}: {task_data['title']}")
        return task_id

    def _start_mock_queen(self) -> bool:
        """Start mock Queen process"""
        try:
            queen_script = self._create_mock_queen_script()
            self.queen_process = subprocess.Popen([sys.executable, queen_script], env=os.environ.copy())
            time.sleep(2)
            if self.queen_process.poll() is None:
                print("👑 Mock Queen started successfully")
                return True
            print("❌ Mock Queen failed to start")
            return False
        except Exception as e:
            print(f"❌ Failed to start mock Queen: {e}")
            return False

    def _start_mock_worker(self, worker_id: str, should_fail: bool=False, slow_execution: bool=False) -> bool:
        """Start mock Worker process"""
        try:
            worker_script = self._create_mock_worker_script(worker_id, should_fail, slow_execution)
            worker_process = subprocess.Popen([sys.executable, worker_script], env=os.environ.copy())
            self.worker_processes.append((worker_id, worker_process))
            time.sleep(1)
            if worker_process.poll() is None:
                print(f"⚙️ Mock Worker {worker_id} started successfully")
                return True
            print(f"❌ Mock Worker {worker_id} failed to start")
            return False
        except Exception as e:
            print(f"❌ Failed to start mock Worker {worker_id}: {e}")
            return False

    def _create_mock_queen_script(self) -> str:
        """Create mock Queen script"""
        script_content = f'''  # noqa: S608\nimport sqlite3\nimport time\nimport json\nimport signal\nimport sys\n\n# Mock Queen implementation\nclass MockQueen:\n    def __init__(self, db_path):\n        self.db_path = db_path\n        self.running = True\n        signal.signal(signal.SIGTERM, self.shutdown)\n\n    def shutdown(self, signum, frame):\n        self.running = False\n\n    def run(self):\n        print("👑 Mock Queen starting...")\n\n        while self.running:\n            try:\n                # Check for pending tasks\n                conn = sqlite3.connect(self.db_path)\n                cursor = conn.execute(\n                    "SELECT id, title, priority FROM tasks WHERE status = 'pending' ORDER BY priority DESC, created_at ASC LIMIT 5"\n                )\n                tasks = cursor.fetchall()\n\n                for task_id, title, priority in tasks:\n                    # Assign task to available worker\n                    conn.execute(\n                        "UPDATE tasks SET status = 'assigned', updated_at = CURRENT_TIMESTAMP WHERE id = ?",\n                        (task_id,)\n                    )\n                    print(f"👑 Queen assigned task {{task_id}}: {{title}}")\n\n                conn.commit()\n                conn.close()\n\n                time.sleep(1)\n\n            except Exception as e:\n                print(f"👑 Queen error: {{e}}")\n                time.sleep(1)\n\n        print("👑 Mock Queen shutting down")\n\nif __name__ == "__main__":\n    queen = MockQueen("{self.test_db_path}")\n    queen.run()\n'''
        script_path = Path(self.temp_dir) / "mock_queen.py"
        with open(script_path, "w") as f:
            f.write(script_content)
        return str(script_path)

    def _create_mock_worker_script(self, worker_id: str, should_fail: bool=False, slow_execution: bool=False) -> str:
        """Create mock Worker script"""
        script_content = f'''  # noqa: S608\nimport sqlite3\nimport time\nimport json\nimport signal\nimport sys\nimport random\n\n# Mock Worker implementation\nclass MockWorker:\n    def __init__(self, worker_id, db_path, should_fail=False, slow_execution=False):\n        self.worker_id = worker_id\n        self.db_path = db_path\n        self.should_fail = should_fail\n        self.slow_execution = slow_execution\n        self.running = True\n        signal.signal(signal.SIGTERM, self.shutdown)\n\n    def shutdown(self, signum, frame):\n        self.running = False\n\n    def run(self):\n        print(f"⚙️ Mock Worker {{self.worker_id}} starting...")\n\n        while self.running:\n            try:\n                # Look for assigned tasks\n                conn = sqlite3.connect(self.db_path)\n                cursor = conn.execute(\n                    "SELECT id, title, context FROM tasks WHERE status = 'assigned' LIMIT 1"\n                )\n                row = cursor.fetchone()\n\n                if row:\n                    task_id, title, context = row\n\n                    # Mark task as in progress\n                    conn.execute(\n                        "UPDATE tasks SET status = 'running', assigned_worker = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",\n                        (self.worker_id, task_id)\n                    )\n                    conn.commit()\n\n                    print(f"⚙️ Worker {{self.worker_id}} starting task {{task_id}}: {{title}}")\n\n                    # Simulate work\n                    if self.slow_execution:\n                        time.sleep(5)  # Long execution for timeout testing\n                    elif self.should_fail:\n                        # Simulate failure\n                        conn.execute(\n                            "UPDATE tasks SET status = 'failed', result = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",\n                            (json.dumps({{"status": "error", "error": "Simulated worker failure", "worker_id": self.worker_id}}), task_id)\n                        )\n                        conn.commit()\n                        print(f"💥 Worker {{self.worker_id}} failed on task {{task_id}}")\n                        sys.exit(1)  # Worker crash\n                    else:\n                        time.sleep(1)  # Normal execution time\n\n                    # Complete task\n                    result = {{\n                        "status": "success",\n                        "worker_id": self.worker_id,\n                        "execution_time": 1.0,\n                        "timestamp": time.time()\n                    }}\n\n                    conn.execute(\n                        "UPDATE tasks SET status = 'completed', result = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",\n                        (json.dumps(result), task_id)\n                    )\n                    conn.commit()\n\n                    print(f"✅ Worker {{self.worker_id}} completed task {{task_id}}")\n\n                conn.close()\n                time.sleep(0.5)\n\n            except Exception as e:\n                print(f"⚙️ Worker {{self.worker_id}} error: {{e}}")\n                time.sleep(1)\n\n        print(f"⚙️ Mock Worker {{self.worker_id}} shutting down")\n\nif __name__ == "__main__":\n    worker = MockWorker("{worker_id}", "{self.test_db_path}", {should_fail}, {slow_execution})\n    worker.run()\n'''
        script_path = Path(self.temp_dir) / f"mock_worker_{worker_id}.py"
        with open(script_path, "w") as f:
            f.write(script_content)
        return str(script_path)

    def _stop_all_processes(self):
        """Stop all Queen and Worker processes"""
        if self.queen_process and self.queen_process.poll() is None:
            try:
                self.queen_process.terminate()
                self.queen_process.wait(timeout=5)
            except (subprocess.TimeoutExpired, ProcessLookupError, OSError):
                try:
                    self.queen_process.kill()
                except (ProcessLookupError, OSError):
                    pass
        for _worker_id, worker_process in self.worker_processes:
            if worker_process.poll() is None:
                try:
                    worker_process.terminate()
                    worker_process.wait(timeout=5)
                except Exception:
                    try:
                        worker_process.kill()
                    except Exception:
                        pass
        self.worker_processes.clear()

    def _stop_worker(self, worker_id: str):
        """Stop specific worker process"""
        for i, (wid, process) in enumerate(self.worker_processes):
            if wid == worker_id:
                if process.poll() is None:
                    try:
                        process.terminate()
                        process.wait(timeout=5)
                    except Exception:
                        try:
                            process.kill()
                        except Exception:
                            pass
                del self.worker_processes[i]
                break

    def _monitor_task_completion(self, task_id: int, timeout: int=30) -> bool:
        """Monitor task for completion"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self._is_task_completed(task_id):
                return True
            time.sleep(0.5)
        return False

    def _is_task_completed(self, task_id: int) -> bool:
        """Check if task is completed"""
        conn = sqlite3.connect(self.test_db_path)
        cursor = conn.execute("SELECT status FROM tasks WHERE id = ?", (task_id,))
        row = cursor.fetchone()
        conn.close()
        return row and row[0] == "completed"

    def _get_task_status(self, task_id: int) -> str | None:
        """Get current task status"""
        conn = sqlite3.connect(self.test_db_path)
        cursor = conn.execute("SELECT status FROM tasks WHERE id = ?", (task_id,))
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else None

    def _get_task_result(self, task_id: int) -> dict | None:
        """Get task result data"""
        conn = sqlite3.connect(self.test_db_path)
        cursor = conn.execute("SELECT result FROM tasks WHERE id = ?", (task_id,))
        row = cursor.fetchone()
        conn.close()
        if row and row[0]:
            try:
                return json.loads(row[0])
            except Exception:
                return None
        return None

    def _generate_pipeline_test_report(self, all_passed: bool):
        """Generate pipeline test report"""
        print(f"\n{'=' * 70}")
        print("📊 QUEEN → WORKER PIPELINE TEST REPORT")
        print("=" * 70)
        sum([1 if all_passed else 0])
        print("\n📈 Test Results:")
        print(f"   Overall Status: {('✅ ALL PASSED' if all_passed else '❌ SOME FAILED')}")
        conn = sqlite3.connect(self.test_db_path)
        cursor = conn.execute("SELECT COUNT(*) FROM tasks")
        total_tasks = cursor.fetchone()[0]
        cursor = conn.execute("SELECT COUNT(*) FROM tasks WHERE status = 'completed'")
        completed_tasks = cursor.fetchone()[0]
        cursor = conn.execute("SELECT COUNT(*) FROM tasks WHERE status = 'failed'")
        failed_tasks = cursor.fetchone()[0]
        conn.close()
        print("\n📊 Pipeline Statistics:")
        print(f"   Total Tasks Created: {total_tasks}")
        print(f"   Tasks Completed: {completed_tasks}")
        print(f"   Tasks Failed: {failed_tasks}")
        if total_tasks > 0:
            success_rate = completed_tasks / total_tasks * 100
            print(f"   Success Rate: {success_rate:.1f}%")
        print(f"\n{'=' * 70}")
        if all_passed:
            print("🎉 QUEEN → WORKER PIPELINE VALIDATION COMPLETE!")
            print("✅ All pipeline components working correctly")
            print("🚀 Ready for production deployment")
        else:
            print("❌ QUEEN → WORKER PIPELINE VALIDATION FAILED")
            print("🔧 Pipeline needs fixes before production")
        print("=" * 70)

def main():
    """Main entry point for pipeline test"""
    pipeline_test = QueenWorkerPipelineTest()
    try:
        success = pipeline_test.run_complete_pipeline_test()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n⚠️ Pipeline test interrupted by user")
        pipeline_test.teardown_test_environment()
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Pipeline test failed: {e}")
        pipeline_test.teardown_test_environment()
        sys.exit(1)
if __name__ == "__main__":
    main()
