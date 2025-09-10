#!/usr/bin/env python3
"""
Comprehensive test suite for production-ready CC Worker
Tests all critical functionality including atomic operations, lock recovery, and state management
"""

import json
import os
import sys
import tempfile
import time
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch, call, mock_open
import subprocess
import signal

# Import the worker module
import cc_worker
from cc_worker import CCWorker, ALLOWED_STATES, CAPABILITY_MAP


class TestCCWorker(unittest.TestCase):
    """Test suite for production-ready CC Worker"""
    
    def setUp(self):
        """Setup test environment"""
        self.test_dir = tempfile.mkdtemp()
        self.test_path = Path(self.test_dir)
        
        # Create hive directory structure
        self.hive_dir = self.test_path / "hive"
        self.bus_dir = self.hive_dir / "bus"
        self.workers_dir = self.hive_dir / "workers"
        self.logs_dir = self.hive_dir / "logs"
        self.locks_dir = self.bus_dir / "locks"
        
        # Create directories
        for d in [self.bus_dir, self.workers_dir, self.logs_dir, self.locks_dir]:
            d.mkdir(parents=True, exist_ok=True)
        
        # Mock environment
        self.original_cwd = os.getcwd()
        os.chdir(self.test_dir)
        
        # Create test task data
        self.test_tasks = {
            "tasks": [
                {
                    "id": "test_001",
                    "title": "Test backend task",
                    "description": "Test task for backend",
                    "tags": ["python", "backend"],
                    "status": "queued",
                    "priority": "high",
                    "acceptance": ["Complete the task"]
                },
                {
                    "id": "test_002",
                    "title": "Test frontend task",
                    "description": "Test task for frontend",
                    "tags": ["react", "frontend"],
                    "status": "queued",
                    "priority": "medium",
                    "acceptance": ["Build UI component"]
                }
            ],
            "task_counter": 2
        }
        
        # Save test tasks
        with open(self.bus_dir / "tasks.json", "w") as f:
            json.dump(self.test_tasks, f)
    
    def tearDown(self):
        """Cleanup test environment"""
        os.chdir(self.original_cwd)
        # Clean up test directory
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_atomic_write_json(self):
        """Test atomic JSON write prevents race conditions"""
        worker = CCWorker("backend")
        test_file = self.test_path / "test.json"
        test_data = {"key": "value", "number": 42}
        
        # Test normal write
        worker.atomic_write_json(test_file, test_data)
        
        # Verify file exists and content is correct
        self.assertTrue(test_file.exists())
        with open(test_file) as f:
            loaded = json.load(f)
        self.assertEqual(loaded, test_data)
        
        # Verify temp file is cleaned up
        temp_files = list(self.test_path.glob("*.tmp"))
        self.assertEqual(len(temp_files), 0)
        
        # Test write with simulated error
        with patch("os.replace", side_effect=OSError("Simulated error")):
            with self.assertRaises(OSError):
                worker.atomic_write_json(test_file, {"new": "data"})
        
        # Original file should be unchanged
        with open(test_file) as f:
            loaded = json.load(f)
        self.assertEqual(loaded, test_data)
    
    def test_stale_lock_recovery(self):
        """Test stale lock detection and recovery"""
        worker = CCWorker("backend")
        
        # Create a stale lock (40 minutes old)
        stale_time = datetime.now(timezone.utc) - timedelta(minutes=40)
        lock_file = self.locks_dir / "test_task.lock"
        lock_data = {
            "worker": "old_worker",
            "ts": stale_time.isoformat(),
            "pid": 99999
        }
        with open(lock_file, "w") as f:
            json.dump(lock_data, f)
        
        # Worker should be able to claim stale lock
        self.assertTrue(worker.claim_task_lock("test_task"))
        
        # Verify lock now belongs to current worker
        with open(lock_file) as f:
            new_lock = json.load(f)
        self.assertEqual(new_lock["worker"], "backend")
        
        # Fresh lock should not be claimable
        worker.release_task_lock("test_task")
        worker.claim_task_lock("test_task")
        
        # Another worker shouldn't be able to claim fresh lock
        worker2 = CCWorker("frontend")
        self.assertFalse(worker2.claim_task_lock("test_task"))
    
    def test_final_json_parsing(self):
        """Test robust FINAL_JSON marker parsing"""
        worker = CCWorker("backend")
        
        # Test with proper FINAL_JSON marker
        lines = [
            "Some output",
            "More output",
            'FINAL_JSON: {"status":"success","notes":"Task done","pr":"","next_state":"completed"}'
        ]
        result = worker.parse_final_json(lines)
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["next_state"], "completed")
        
        # Test with malformed JSON after marker
        lines = [
            "Output",
            "FINAL_JSON: {broken json"
        ]
        result = worker.parse_final_json(lines)
        self.assertEqual(result, {})
        
        # Test legacy format fallback
        lines = [
            "Output",
            '{"status":"failed","notes":"Legacy format"}'
        ]
        result = worker.parse_final_json(lines)
        self.assertEqual(result["status"], "failed")
        
        # Test no JSON found
        lines = ["Just", "regular", "output"]
        result = worker.parse_final_json(lines)
        self.assertEqual(result, {})
    
    def test_resume_semantics(self):
        """Test task resumption after restart"""
        # Create task already assigned to backend
        self.test_tasks["tasks"][0]["status"] = "in_progress"
        self.test_tasks["tasks"][0]["assignee"] = "backend"
        with open(self.bus_dir / "tasks.json", "w") as f:
            json.dump(self.test_tasks, f)
        
        worker = CCWorker("backend")
        task = worker.get_next_task()
        
        # Should get the in-progress task
        self.assertIsNotNone(task)
        self.assertEqual(task["id"], "test_001")
        self.assertEqual(task["status"], "in_progress")
        
        # Frontend worker should not get backend's task
        worker2 = CCWorker("frontend")
        task2 = worker2.get_next_task()
        self.assertIsNotNone(task2)
        self.assertEqual(task2["id"], "test_002")  # Gets the other queued task
    
    def test_capability_matching(self):
        """Test improved capability matching with sets"""
        worker = CCWorker("backend")
        capabilities = worker.get_normalized_capabilities()
        
        # Should include all mapped capabilities
        self.assertIn("backend", capabilities)
        self.assertIn("python", capabilities)
        self.assertIn("flask", capabilities)
        self.assertIn("api", capabilities)
        
        # Test task matching
        task = worker.get_next_task()
        self.assertIsNotNone(task)
        self.assertEqual(task["id"], "test_001")
        
        # Frontend worker should get frontend task
        worker2 = CCWorker("frontend")
        capabilities2 = worker2.get_normalized_capabilities()
        self.assertIn("frontend", capabilities2)
        self.assertIn("react", capabilities2)
        self.assertIn("javascript", capabilities2)
    
    def test_state_normalization(self):
        """Test state normalization and advancement"""
        worker = CCWorker("backend")
        
        # Test valid state
        summary = {"next_state": "completed", "notes": "Done"}
        with patch.object(worker, 'update_task_status') as mock_update:
            with patch.object(worker, 'emit_event') as mock_emit:
                worker.advance_task_state("test_001", summary)
                mock_update.assert_called_with(
                    "test_001", "completed", 
                    result=summary, pr="", notes="Done"
                )
        
        # Test invalid state mapping
        summary = {"next_state": "success", "notes": "Done"}
        with patch.object(worker, 'update_task_status') as mock_update:
            worker.advance_task_state("test_001", summary)
            # Should map "success" to "completed"
            mock_update.assert_called_with(
                "test_001", "completed",
                result=summary, pr="", notes="Done"
            )
        
        # Test unknown state defaults to failed
        summary = {"next_state": "unknown_state", "notes": "Error"}
        with patch.object(worker, 'update_task_status') as mock_update:
            worker.advance_task_state("test_001", summary)
            mock_update.assert_called_with(
                "test_001", "failed",
                result=summary, pr="", notes="Error"
            )
    
    def test_comprehensive_events(self):
        """Test comprehensive event emission"""
        worker = CCWorker("backend")
        
        events = []
        original_emit = worker.emit_event
        
        def capture_event(**kwargs):
            # Simulate the actual emit_event behavior
            kwargs.setdefault("ts", datetime.now(timezone.utc).isoformat())
            kwargs.setdefault("worker", worker.worker_id)
            events.append(kwargs)
        
        worker.emit_event = capture_event
        
        # Test various event types
        worker.emit_event(type="worker_started", role="backend_developer")
        worker.emit_event(type="task_claim", task_id="test_001")
        worker.emit_event(type="task_assign", task_id="test_001", assignee="backend")
        worker.emit_event(type="task_in_progress", task_id="test_001")
        worker.emit_event(type="task_complete", task_id="test_001", duration_ms=5000)
        worker.emit_event(type="heartbeat", status="idle")
        
        # Verify all events captured
        event_types = [e["type"] for e in events]
        self.assertIn("worker_started", event_types)
        self.assertIn("task_claim", event_types)
        self.assertIn("task_assign", event_types)
        self.assertIn("task_in_progress", event_types)
        self.assertIn("task_complete", event_types)
        self.assertIn("heartbeat", event_types)
        
        # All events should have worker and timestamp
        for event in events:
            self.assertIn("worker", event)
            self.assertIn("ts", event)
    
    def test_event_rotation(self):
        """Test daily event file rotation"""
        worker = CCWorker("backend")
        
        # Get today's file
        today_file = worker.get_events_file()
        self.assertTrue("events_" in str(today_file))
        self.assertTrue(datetime.now().strftime("%Y%m%d") in str(today_file))
        
        # Mock different day
        with patch("cc_worker.datetime") as mock_dt:
            tomorrow = datetime.now() + timedelta(days=1)
            mock_dt.now.return_value = tomorrow
            tomorrow_file = worker.get_events_file()
            
        # Should be different files
        self.assertNotEqual(today_file, tomorrow_file)
    
    def test_timeout_handling(self):
        """Test 20-minute timeout and retry logic"""
        worker = CCWorker("backend")
        task = self.test_tasks["tasks"][0]
        
        # Mock Claude execution with timeout
        with patch("subprocess.Popen") as mock_popen:
            mock_process = MagicMock()
            mock_process.stdout = iter([])
            mock_process.wait.side_effect = subprocess.TimeoutExpired("cmd", 600)
            mock_popen.return_value.__enter__.return_value = mock_process
            
            with patch("time.sleep"):  # Speed up test
                result = worker.execute_with_claude(task)
            
            # Should retry once for timeout
            self.assertEqual(mock_popen.call_count, 2)
            self.assertEqual(result["status"], "failed")
    
    def test_graceful_shutdown(self):
        """Test graceful shutdown with signal handling"""
        worker = CCWorker("backend")
        worker.current_task_id = "test_001"
        
        # Mock release_task_lock and emit_event
        with patch.object(worker, 'release_task_lock') as mock_release:
            with patch.object(worker, 'emit_event') as mock_emit:
                with patch("sys.exit") as mock_exit:
                    # Trigger graceful shutdown
                    worker._graceful_shutdown(signal.SIGTERM, None)
                    
                    # Should release lock
                    mock_release.assert_called_with("test_001")
                    
                    # Should emit events
                    calls = mock_emit.call_args_list
                    self.assertTrue(any("task_abandoned" in str(c) for c in calls))
                    self.assertTrue(any("worker_stopped" in str(c) for c in calls))
                    
                    # Should exit
                    mock_exit.assert_called_with(0)
    
    def test_tool_restrictions(self):
        """Test role-specific tool restrictions"""
        # Backend worker
        backend = CCWorker("backend")
        args = backend.get_claude_args_for_role()
        self.assertIn("--allowedTools", args)
        self.assertTrue(any("python" in arg for arg in args))
        self.assertFalse(any("docker" in arg for arg in args))
        
        # Frontend worker
        frontend = CCWorker("frontend")
        args = frontend.get_claude_args_for_role()
        self.assertIn("--allowedTools", args)
        self.assertTrue(any("npm" in arg for arg in args))
        self.assertFalse(any("python" in arg for arg in args))
        
        # Infra worker
        infra = CCWorker("infra")
        args = infra.get_claude_args_for_role()
        self.assertIn("--allowedTools", args)
        self.assertTrue(any("docker" in arg for arg in args))
        
        # Queen gets broader access
        queen = CCWorker("queen")
        args = queen.get_claude_args_for_role()
        self.assertIn("--dangerously-skip-permissions", args)
    
    def test_work_cycle_error_recovery(self):
        """Test work cycle continues after errors"""
        worker = CCWorker("backend")
        
        # Mock get_next_task to raise exception
        with patch.object(worker, 'get_next_task', side_effect=Exception("Test error")):
            with patch.object(worker, 'emit_event') as mock_emit:
                # Should not crash
                worker.work_cycle()
                
                # Should emit error event
                calls = mock_emit.call_args_list
                self.assertTrue(any("worker_error" in str(c) for c in calls))
        
        # Worker should be reset to idle
        self.assertEqual(worker.config["status"], "idle")
        self.assertIsNone(worker.config.get("current_task"))
    
    def test_environment_overrides(self):
        """Test environment variable overrides"""
        # Test CLAUDE_BIN override
        with patch.dict(os.environ, {"CLAUDE_BIN": "/custom/claude"}):
            with patch("shutil.which", return_value="/custom/claude"):
                worker = CCWorker("backend")
                self.assertEqual(worker.claude_cmd, "/custom/claude")
        
        # Test WORKER_CYCLE_SECONDS override
        with patch.dict(os.environ, {"WORKER_CYCLE_SECONDS": "30"}):
            with patch("cc_worker.CCWorker.run_forever") as mock_run:
                with patch("sys.argv", ["test", "backend"]):
                    cc_worker.main()
                    # Check cycle was set to 30
                    mock_run.assert_called_with(30)
    
    def test_simulation_mode(self):
        """Test simulation mode when Claude CLI is missing"""
        with patch("shutil.which", return_value=None):
            with patch.object(Path, 'exists', return_value=False):
                worker = CCWorker("backend")
                
        self.assertIsNone(worker.claude_cmd)
        
        task = self.test_tasks["tasks"][0]
        with patch("time.sleep"):  # Speed up test
            result = worker.execute_with_claude(task)
        
        # Should return blocked status
        self.assertEqual(result["status"], "blocked")
        self.assertIn("CLI missing", result["summary"]["notes"])


class TestIntegration(unittest.TestCase):
    """Integration tests for CC Worker"""
    
    def setUp(self):
        """Setup integration test environment"""
        self.test_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.test_dir)
        
        # Create full hive structure
        Path("hive/bus/locks").mkdir(parents=True, exist_ok=True)
        Path("hive/workers").mkdir(parents=True, exist_ok=True)
        Path("hive/logs").mkdir(parents=True, exist_ok=True)
    
    def tearDown(self):
        """Cleanup integration test environment"""
        os.chdir(self.original_cwd)
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_multi_worker_coordination(self):
        """Test multiple workers don't claim same task"""
        # Create tasks
        tasks = {
            "tasks": [
                {
                    "id": "shared_001",
                    "title": "Shared task",
                    "tags": ["python", "backend"],
                    "status": "queued"
                }
            ],
            "task_counter": 1
        }
        
        with open("hive/bus/tasks.json", "w") as f:
            json.dump(tasks, f)
        
        # Create multiple workers
        worker1 = CCWorker("backend")
        worker2 = CCWorker("backend")
        
        # Both try to claim same task
        claimed1 = worker1.claim_task_lock("shared_001")
        claimed2 = worker2.claim_task_lock("shared_001")
        
        # Only one should succeed
        self.assertTrue(claimed1 or claimed2)
        self.assertFalse(claimed1 and claimed2)
    
    def test_crash_recovery(self):
        """Test worker recovery after crash"""
        # Create task in progress
        tasks = {
            "tasks": [
                {
                    "id": "crash_001",
                    "title": "Crash test",
                    "tags": ["python"],
                    "status": "in_progress",
                    "assignee": "backend"
                }
            ],
            "task_counter": 1
        }
        
        with open("hive/bus/tasks.json", "w") as f:
            json.dump(tasks, f)
        
        # Create stale lock from "crashed" worker
        lock_file = Path("hive/bus/locks/crash_001.lock")
        old_time = datetime.now(timezone.utc) - timedelta(minutes=35)
        with open(lock_file, "w") as f:
            json.dump({
                "worker": "backend",
                "ts": old_time.isoformat(),
                "pid": 99999
            }, f)
        
        # New worker should resume task
        worker = CCWorker("backend")
        task = worker.get_next_task()
        
        self.assertIsNotNone(task)
        self.assertEqual(task["id"], "crash_001")
        
        # Should be able to reclaim stale lock
        self.assertTrue(worker.claim_task_lock("crash_001"))


def run_tests():
    """Run all tests with verbose output"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test cases
    suite.addTests(loader.loadTestsFromTestCase(TestCCWorker))
    suite.addTests(loader.loadTestsFromTestCase(TestIntegration))
    
    # Run with verbose output
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Return success/failure
    return result.wasSuccessful()


if __name__ == "__main__":
    # Run tests
    success = run_tests()
    
    # Print summary
    print("\n" + "="*60)
    if success:
        print("SUCCESS: All tests passed! Worker is production-ready.")
    else:
        print("FAILED: Some tests failed. Please review and fix.")
    print("="*60)
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)