#!/usr/bin/env python3
"""
Hive Headless MAS Test Suite
Comprehensive testing for the autonomous development system
"""

import json
import time
import pathlib
import subprocess
import tempfile
import threading
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class HiveMASTestSuite:
    """Comprehensive test suite for Hive headless MAS"""
    
    def __init__(self, root_dir: str = "."):
        self.root = pathlib.Path(root_dir).resolve()
        self.hive_dir = self.root / "hive"
        self.test_results = []
        self.start_time = datetime.now()
        
    def log_test_result(self, test_name: str, passed: bool, details: str = "", execution_time: float = 0):
        """Log a test result"""
        result = {
            "test_name": test_name,
            "passed": passed,
            "details": details,
            "execution_time": execution_time,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        self.test_results.append(result)
        
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} {test_name} ({execution_time:.2f}s)")
        if details:
            print(f"     {details}")
    
    def test_directory_structure(self):
        """Test that all required directories exist"""
        start = time.time()
        
        required_dirs = [
            self.hive_dir / "bus",
            self.hive_dir / "workers",
            self.hive_dir / "spec",
            self.hive_dir / "logs"
        ]
        
        missing_dirs = []
        for dir_path in required_dirs:
            if not dir_path.exists():
                missing_dirs.append(str(dir_path))
        
        passed = len(missing_dirs) == 0
        details = f"Missing directories: {missing_dirs}" if missing_dirs else "All directories present"
        
        self.log_test_result("Directory Structure", passed, details, time.time() - start)
    
    def test_configuration_files(self):
        """Test that all configuration files are valid"""
        start = time.time()
        
        config_files = [
            (self.hive_dir / "bus" / "tasks.json", "tasks"),
            (self.hive_dir / "workers" / "queen.json", "queen worker"),
            (self.hive_dir / "workers" / "frontend.json", "frontend worker"),
            (self.hive_dir / "workers" / "backend.json", "backend worker"),
            (self.hive_dir / "workers" / "infra.json", "infra worker")
        ]
        
        invalid_files = []
        for file_path, description in config_files:
            try:
                if file_path.exists():
                    with open(file_path, "r", encoding="utf-8") as f:
                        json.load(f)
                else:
                    invalid_files.append(f"{description} (missing)")
            except json.JSONDecodeError as e:
                invalid_files.append(f"{description} (invalid JSON: {e})")
        
        passed = len(invalid_files) == 0
        details = f"Invalid files: {invalid_files}" if invalid_files else "All configuration files valid"
        
        self.log_test_result("Configuration Files", passed, details, time.time() - start)
    
    def test_worker_configs(self):
        """Test worker configurations for completeness"""
        start = time.time()
        
        required_fields = ["worker_id", "role", "capabilities", "config"]
        issues = []
        
        for worker_file in (self.hive_dir / "workers").glob("*.json"):
            try:
                with open(worker_file, "r", encoding="utf-8") as f:
                    config = json.load(f)
                
                # Check required fields
                missing_fields = [field for field in required_fields if field not in config]
                if missing_fields:
                    issues.append(f"{worker_file.stem}: missing {missing_fields}")
                
                # Check capabilities is a list
                if "capabilities" in config and not isinstance(config["capabilities"], list):
                    issues.append(f"{worker_file.stem}: capabilities must be a list")
                
                # Check Claude args exist
                claude_args = config.get("config", {}).get("claude_args", [])
                if not isinstance(claude_args, list):
                    issues.append(f"{worker_file.stem}: claude_args must be a list")
                
            except (FileNotFoundError, json.JSONDecodeError) as e:
                issues.append(f"{worker_file.stem}: {str(e)}")
        
        passed = len(issues) == 0
        details = f"Configuration issues: {issues}" if issues else "All worker configs valid"
        
        self.log_test_result("Worker Configurations", passed, details, time.time() - start)
    
    def test_task_queue_operations(self):
        """Test task queue creation, loading, and manipulation"""
        start = time.time()
        
        try:
            # Import the orchestrator to test its functions
            import orchestrator
            
            # Create test orchestrator instance
            orch = orchestrator.HiveOrchestrator(str(self.root))
            
            # Test task creation
            initial_tasks = orch.load_tasks()
            initial_count = len(initial_tasks.get("tasks", []))
            
            # Create a test task
            task_id = orch.create_task(
                "Test task for validation",
                "This is a test task created by the test suite",
                tags=["test"],
                priority="low",
                acceptance_criteria=["Task created successfully", "Task appears in queue"]
            )
            
            # Verify task was created
            updated_tasks = orch.load_tasks()
            new_count = len(updated_tasks.get("tasks", []))
            
            # Find the created task
            created_task = None
            for task in updated_tasks.get("tasks", []):
                if task["id"] == task_id:
                    created_task = task
                    break
            
            if created_task and new_count == initial_count + 1:
                passed = True
                details = f"Task {task_id} created successfully"
            else:
                passed = False
                details = f"Task creation failed. Count: {initial_count} -> {new_count}, Task found: {created_task is not None}"
            
        except Exception as e:
            passed = False
            details = f"Error testing task queue: {str(e)}"
        
        self.log_test_result("Task Queue Operations", passed, details, time.time() - start)
    
    def test_cli_functionality(self):
        """Test CLI commands for basic functionality"""
        start = time.time()
        
        try:
            # Test CLI status command
            result = subprocess.run([
                "python", "hive_cli.py", "status", "--json"
            ], cwd=str(self.root), capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                # Try to parse JSON output
                status_data = json.loads(result.stdout)
                if "tasks" in status_data and "workers" in status_data:
                    passed = True
                    details = "CLI status command working correctly"
                else:
                    passed = False
                    details = "CLI status returned invalid data structure"
            else:
                passed = False
                details = f"CLI status failed: {result.stderr}"
                
        except subprocess.TimeoutExpired:
            passed = False
            details = "CLI command timed out"
        except json.JSONDecodeError:
            passed = False
            details = "CLI returned invalid JSON"
        except Exception as e:
            passed = False
            details = f"CLI test error: {str(e)}"
        
        self.log_test_result("CLI Functionality", passed, details, time.time() - start)
    
    def test_safety_manager(self):
        """Test safety manager functionality"""
        start = time.time()
        
        try:
            import safety_manager
            
            # Create safety manager instance
            safety = safety_manager.SafetyManager(str(self.root))
            
            # Test configuration loading
            config = safety.load_safety_config()
            if not isinstance(config, dict) or "max_concurrent_workers" not in config:
                passed = False
                details = "Safety configuration invalid"
            else:
                # Test command validation
                valid, msg = safety.validate_claude_command(
                    ["claude", "--add-dir", "."],
                    "Create a simple hello world function"
                )
                
                if valid:
                    # Test blocked command detection
                    blocked, block_msg = safety.validate_claude_command(
                        ["claude", "--dangerously-skip-permissions"],
                        "Execute: rm -rf /"
                    )
                    
                    if not blocked:
                        passed = True
                        details = "Safety validation working correctly"
                    else:
                        passed = False
                        details = f"Blocked command not detected: {block_msg}"
                else:
                    passed = False
                    details = f"Valid command rejected: {msg}"
        
        except Exception as e:
            passed = False
            details = f"Safety manager test error: {str(e)}"
        
        self.log_test_result("Safety Manager", passed, details, time.time() - start)
    
    def test_worker_process(self):
        """Test worker process initialization (without full execution)"""
        start = time.time()
        
        try:
            import headless_workers
            
            # Create worker instance
            worker = headless_workers.HeadlessWorker("queen", str(self.root))
            
            # Test configuration loading
            if worker.config and "worker_id" in worker.config:
                # Test task prompt generation
                test_task = {
                    "id": "test_001",
                    "title": "Test task",
                    "description": "Test task for worker validation",
                    "tags": ["test"],
                    "acceptance_criteria": ["Task completes successfully"]
                }
                
                prompt = worker.create_task_prompt(test_task)
                
                if prompt and len(prompt) > 50:  # Reasonable prompt length
                    passed = True
                    details = "Worker initialization and prompt generation working"
                else:
                    passed = False
                    details = f"Invalid prompt generated: length {len(prompt)}"
            else:
                passed = False
                details = "Worker configuration not loaded properly"
        
        except Exception as e:
            passed = False
            details = f"Worker process test error: {str(e)}"
        
        self.log_test_result("Worker Process", passed, details, time.time() - start)
    
    def test_git_operations(self):
        """Test git operations and branch management"""
        start = time.time()
        
        try:
            # Check if we're in a git repository
            result = subprocess.run([
                "git", "status"
            ], cwd=str(self.root), capture_output=True, text=True)
            
            if result.returncode != 0:
                passed = False
                details = "Not in a git repository"
            else:
                # Check if we can create a test branch
                test_branch = f"test-branch-{uuid.uuid4().hex[:8]}"
                
                # Create test branch
                create_result = subprocess.run([
                    "git", "checkout", "-b", test_branch
                ], cwd=str(self.root), capture_output=True, text=True)
                
                if create_result.returncode == 0:
                    # Switch back to main and delete test branch
                    subprocess.run([
                        "git", "checkout", "main"
                    ], cwd=str(self.root), capture_output=True)
                    
                    subprocess.run([
                        "git", "branch", "-D", test_branch
                    ], cwd=str(self.root), capture_output=True)
                    
                    passed = True
                    details = "Git operations working correctly"
                else:
                    passed = False
                    details = f"Failed to create test branch: {create_result.stderr}"
        
        except Exception as e:
            passed = False
            details = f"Git operations test error: {str(e)}"
        
        self.log_test_result("Git Operations", passed, details, time.time() - start)
    
    def test_claude_cli_availability(self):
        """Test that Claude CLI is available and working"""
        start = time.time()
        
        try:
            # Check if Claude CLI is in PATH
            import shutil
            claude_path = shutil.which("claude")
            
            if not claude_path:
                passed = False
                details = "Claude CLI not found in PATH"
            else:
                # Test Claude CLI with --help
                result = subprocess.run([
                    "claude", "--help"
                ], capture_output=True, text=True, timeout=10)
                
                if result.returncode == 0:
                    passed = True
                    details = f"Claude CLI available at {claude_path}"
                else:
                    passed = False
                    details = f"Claude CLI error: {result.stderr}"
        
        except subprocess.TimeoutExpired:
            passed = False
            details = "Claude CLI --help timed out"
        except Exception as e:
            passed = False
            details = f"Claude CLI test error: {str(e)}"
        
        self.log_test_result("Claude CLI Availability", passed, details, time.time() - start)
    
    def test_integration_workflow(self):
        """Test a simplified end-to-end workflow"""
        start = time.time()
        
        try:
            import orchestrator
            
            # Create orchestrator
            orch = orchestrator.HiveOrchestrator(str(self.root))
            
            # Create a simple test task
            task_id = orch.create_task(
                "Integration test task",
                "Simple task to test integration workflow",
                tags=["integration", "test"],
                priority="low",
                acceptance_criteria=["Task created", "Task processed by system"]
            )
            
            # Load tasks and verify creation
            tasks_data = orch.load_tasks()
            test_task = None
            for task in tasks_data.get("tasks", []):
                if task["id"] == task_id:
                    test_task = task
                    break
            
            if test_task:
                # Test task assignment (simulate)
                available_workers = orch.get_available_workers()
                
                if available_workers:
                    # Test assignment logic
                    assigned_worker = orch.assign_task(test_task)
                    
                    if assigned_worker:
                        passed = True
                        details = f"Integration workflow working: task assigned to {assigned_worker}"
                    else:
                        passed = False
                        details = "Task assignment failed"
                else:
                    passed = False
                    details = "No available workers found"
            else:
                passed = False
                details = "Test task creation failed"
        
        except Exception as e:
            passed = False
            details = f"Integration workflow error: {str(e)}"
        
        self.log_test_result("Integration Workflow", passed, details, time.time() - start)
    
    def run_all_tests(self):
        """Run all test suites"""
        print("🧪 Starting Hive Headless MAS Test Suite")
        print("=" * 60)
        
        # List of all tests
        tests = [
            self.test_directory_structure,
            self.test_configuration_files,
            self.test_worker_configs,
            self.test_claude_cli_availability,
            self.test_git_operations,
            self.test_task_queue_operations,
            self.test_cli_functionality,
            self.test_safety_manager,
            self.test_worker_process,
            self.test_integration_workflow
        ]
        
        # Run each test
        for test in tests:
            try:
                test()
            except Exception as e:
                self.log_test_result(test.__name__, False, f"Unexpected error: {str(e)}")
        
        # Generate summary
        self.generate_test_report()
    
    def generate_test_report(self):
        """Generate and display test report"""
        total_time = (datetime.now() - self.start_time).total_seconds()
        
        passed_tests = [r for r in self.test_results if r["passed"]]
        failed_tests = [r for r in self.test_results if not r["passed"]]
        
        pass_rate = len(passed_tests) / len(self.test_results) * 100 if self.test_results else 0
        
        print("\n" + "=" * 60)
        print("🧪 TEST SUMMARY")
        print("=" * 60)
        print(f"Total Tests: {len(self.test_results)}")
        print(f"Passed: {len(passed_tests)} ✅")
        print(f"Failed: {len(failed_tests)} ❌")
        print(f"Pass Rate: {pass_rate:.1f}%")
        print(f"Total Time: {total_time:.2f}s")
        
        if failed_tests:
            print("\n❌ FAILED TESTS:")
            for test in failed_tests:
                print(f"   • {test['test_name']}: {test['details']}")
        
        print("\n📊 DETAILED RESULTS:")
        for result in self.test_results:
            status = "✅" if result["passed"] else "❌"
            print(f"   {status} {result['test_name']} ({result['execution_time']:.2f}s)")
        
        # Save detailed report
        report_file = self.hive_dir / "logs" / f"test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        report_file.parent.mkdir(exist_ok=True)
        
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump({
                "summary": {
                    "total_tests": len(self.test_results),
                    "passed": len(passed_tests),
                    "failed": len(failed_tests),
                    "pass_rate": pass_rate,
                    "total_time": total_time
                },
                "test_results": self.test_results
            }, f, indent=2)
        
        print(f"\n📄 Detailed report saved: {report_file}")
        
        # Return overall success
        return len(failed_tests) == 0

def main():
    """Main test entry point"""
    test_suite = HiveMASTestSuite()
    success = test_suite.run_all_tests()
    
    if success:
        print("\n🎉 All tests passed! Hive Headless MAS is ready for deployment.")
        return 0
    else:
        print("\n💥 Some tests failed. Please review and fix issues before deployment.")
        return 1

if __name__ == "__main__":
    exit(main())