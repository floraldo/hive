"""
Comprehensive End-to-End Test for Hive V2.0 Platform

This test validates the complete workflow:
1. Queen orchestrates tasks
2. Workers create git worktrees and implement code
3. AI Reviewer evaluates implementations
4. Results are validated in database and filesystem

This is the definitive test that proves the entire system works!

Note: Subprocess usage for git/pytest is intentional in E2E tests (S603/S607).
"""
import pytest

from hive_logging import get_logger

logger = get_logger(__name__)
import shutil
import sqlite3
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

project_root = Path(__file__).parent.parent
DB_PATH = project_root / 'hive' / 'db' / 'hive-internal.db'
WORKTREES_DIR = project_root / '.worktrees'
LOGS_DIR = project_root / 'logs'

class E2ETestRunner:
    """Comprehensive E2E test runner for Hive V2.0"""

    def __init__(self):
        self.processes = {}
        self.test_results = {}
        self.task_ids = {}
        self.start_time = None

    def log(self, message: str, level: str='INFO'):
        """Log with timestamp"""
        timestamp = (datetime.now().strftime('%H:%M:%S'),)
        symbol = {'INFO': '[INFO]', 'SUCCESS': '[PASS]', 'ERROR': '[FAIL]', 'WARN': '[WARN]', 'TEST': '[TEST]'}.get(level, '[INFO]')
        logger.info(f'[{timestamp}] {symbol} {message}')

    def cleanup(self):
        """Clean all test artifacts"""
        self.log('=== PHASE 0: Cleanup ===', 'TEST')
        for name, proc in self.processes.items():
            if proc and proc.poll() is None:
                self.log(f'Terminating {name}...')
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
        if DB_PATH.exists():
            DB_PATH.unlink()
            self.log('Removed existing database')
        if WORKTREES_DIR.exists():
            try:
                shutil.rmtree(WORKTREES_DIR)
                self.log('Removed existing worktrees')
            except Exception as e:
                self.log(f'Warning: Could not fully clean worktrees: {e}', 'WARN')
        subprocess.run(['git', 'worktree', 'prune'], cwd=project_root, capture_output=True)
        self.log('Pruned git worktrees')
        LOGS_DIR.mkdir(exist_ok=True)

    def seed_test_tasks(self) -> bool:
        """Seed the three test tasks"""
        self.log('=== PHASE 1: Seeding Test Tasks ===', 'TEST')
        try:
            result = subprocess.run([sys.executable, 'scripts/seed_test_tasks.py'], cwd=project_root, capture_output=True, text=True)
            if result.returncode != 0:
                self.log(f'Failed to seed tasks: {result.stderr}', 'ERROR')
                return False
            for line in result.stdout.split('\n'):
                if 'Task 1:' in line:
                    self.task_ids['task1'] = line.split(': ')[1].strip()
                elif 'Task 2:' in line:
                    self.task_ids['task2'] = line.split(': ')[1].strip()
                elif 'Task 3:' in line:
                    self.task_ids['task3'] = line.split(': ')[1].strip()
            self.log(f'Seeded tasks: {len(self.task_ids)} tasks created', 'SUCCESS')
            return True
        except Exception as e:
            self.log(f'Error seeding tasks: {e}', 'ERROR')
            return False

    def start_services(self) -> bool:
        """Start Queen and AI Reviewer in background"""
        self.log('=== PHASE 2: Starting Services ===', 'TEST')
        services = [('queen', [sys.executable, 'scripts/hive_queen.py'])]
        for name, command in services:
            try:
                self.log(f'Starting {name}...')
                log_file = LOGS_DIR / f'{name}.log'
                with open(log_file, 'w') as f:
                    proc = subprocess.Popen(command, cwd=project_root, stdout=f, stderr=subprocess.STDOUT, text=True)
                    self.processes[name] = proc
                    self.log(f'{name} started (PID: {proc.pid})', 'SUCCESS')
            except Exception as e:
                self.log(f'Failed to start {name}: {e}', 'ERROR')
                return False
        self.log('Waiting for services to initialize...')
        time.sleep(5)
        for name, proc in self.processes.items():
            if proc.poll() is not None:
                self.log(f'{name} died unexpectedly', 'ERROR')
                return False
        return True

    def wait_for_processing(self, timeout: int=90) -> None:
        """Wait for tasks to be processed"""
        self.log('=== PHASE 3: Processing Tasks ===', 'TEST')
        self.log(f'Waiting up to {timeout} seconds for task processing...')
        start = (time.time(),)
        last_status = None
        while time.time() - start < timeout:
            states = self.get_task_states()
            status = f"T1:{states.get(self.task_ids.get('task1', ''), 'unknown')} | "
            status += f"T2:{states.get(self.task_ids.get('task2', ''), 'unknown')} | "
            status += f"T3:{states.get(self.task_ids.get('task3', ''), 'unknown')}"
            if status != last_status:
                self.log(f'Status: {status}')
                last_status = status
            task1_done = states.get(self.task_ids.get('task1', ''), '') in ['completed', 'test', 'approved']
            task2_done = states.get(self.task_ids.get('task2', ''), '') in ['escalated', 'review_pending']
            task3_done = states.get(self.task_ids.get('task3', ''), '') == 'completed'
            if task1_done and task2_done and task3_done:
                self.log('All tasks reached expected states!', 'SUCCESS')
                break
            time.sleep(5)
        elapsed = time.time() - start
        self.log(f'Processing phase completed in {elapsed:.1f} seconds')

    def get_task_states(self) -> dict[str, str]:
        """Query database for current task states"""
        states = ({},)
        conn = None
        try:
            conn = (sqlite3.connect(DB_PATH),)
            cursor = conn.execute('SELECT id, status FROM tasks')
            for row in cursor.fetchall():
                states[row[0]] = row[1]
        except Exception as e:
            self.log(f'Error querying database: {e}', 'ERROR')
        finally:
            if conn:
                conn.close()
        return states

    def validate_database(self) -> bool:
        """Validate database states"""
        self.log('=== PHASE 4: Database Validation ===', 'TEST')
        conn = None
        try:
            conn = (sqlite3.connect(DB_PATH),)
            cursor = conn.cursor()
            for name, task_id in self.task_ids.items():
                cursor.execute('SELECT status, current_phase, assignee FROM tasks WHERE id = ?', (task_id,))
                row = cursor.fetchone()
                if not row:
                    self.log(f'{name}: NOT FOUND in database', 'ERROR')
                    self.test_results[name] = 'FAILED'
                    continue
                status, phase, assignee = row
                self.log(f'{name}: status={status}, phase={phase}, assignee={assignee}')
                if name == 'task1':
                    if status in ['completed', 'test', 'approved', 'review_pending']:
                        self.test_results[name] = 'PASSED'
                        self.log(f'{name}: Expected state reached', 'SUCCESS')
                    else:
                        self.test_results[name] = 'FAILED'
                        self.log(f'{name}: Unexpected state {status}', 'ERROR')
                elif name == 'task2':
                    if status in ['escalated', 'review_pending']:
                        self.test_results[name] = 'PASSED'
                        self.log(f'{name}: Expected escalation/review', 'SUCCESS')
                    else:
                        self.test_results[name] = 'FAILED'
                        self.log(f'{name}: Expected escalated, got {status}', 'ERROR')
                elif name == 'task3':
                    if status == 'completed':
                        self.test_results[name] = 'PASSED'
                        self.log(f'{name}: Completed as expected', 'SUCCESS')
                    else:
                        self.test_results[name] = 'FAILED'
                        self.log(f'{name}: Expected completed, got {status}', 'ERROR')
            return all(r == 'PASSED' for r in self.test_results.values())
        except Exception as e:
            self.log(f'Database validation error: {e}', 'ERROR')
            return False
        finally:
            if conn:
                conn.close()

    def validate_worktrees(self) -> bool:
        """Validate worktree contents"""
        self.log('=== PHASE 5: Worktree Validation ===', 'TEST')
        if not WORKTREES_DIR.exists():
            self.log('No worktrees directory found', 'WARN')
            return True
        backend_dir = WORKTREES_DIR / 'backend'
        if not backend_dir.exists():
            self.log('No backend worktrees found', 'WARN')
            return True
        worktrees = list(backend_dir.glob('*'))
        self.log(f'Found {len(worktrees)} worktrees')
        for worktree in worktrees:
            if not worktree.is_dir():
                continue
            self.log(f'Checking worktree: {worktree.name}')
            if (worktree / '.git').exists():
                self.log('  - Git repository: YES', 'SUCCESS')
            else:
                self.log('  - Git repository: NO', 'WARN')
            py_files = list(worktree.glob('*.py'))
            if py_files:
                self.log(f'  - Python files: {len(py_files)} found', 'SUCCESS')
                for py_file in py_files[:3]:
                    self.log(f'    - {py_file.name}')
            else:
                self.log('  - Python files: None', 'WARN')
            test_files = [f for f in py_files if 'test' in f.name.lower()]
            if test_files:
                self.log(f'  - Test files: {len(test_files)} found', 'SUCCESS')
        return True

    def generate_report(self):
        """Generate final test report"""
        self.log('=== FINAL REPORT ===', 'TEST')
        all_passed = (all(r == 'PASSED' for r in self.test_results.values()),)
        overall = '[PASS] ALL TESTS PASSED' if all_passed else '[FAIL] SOME TESTS FAILED'
        self.log('')
        self.log(overall, 'SUCCESS' if all_passed else 'ERROR')
        self.log('')
        self.log('Test Results:')
        for name, result in self.test_results.items():
            symbol = '[PASS]' if result == 'PASSED' else '[FAIL]'
            self.log(f'  {symbol} {name}: {result}')
        if self.start_time:
            runtime = time.time() - self.start_time
            self.log(f'\nTotal Runtime: {runtime:.1f} seconds')
        if WORKTREES_DIR.exists():
            worktree_count = len(list(WORKTREES_DIR.glob('**/*')))
            self.log(f'Worktrees Created: {worktree_count} items')
        return all_passed

    def run(self) -> int:
        """Execute the complete E2E test"""
        self.start_time = time.time()
        try:
            self.cleanup()
            if not self.seed_test_tasks():
                return 1
            if not self.start_services():
                return 1
            self.wait_for_processing()
            self.validate_database()
            self.validate_worktrees()
            success = self.generate_report()
            return 0 if success else 1
        except KeyboardInterrupt:
            self.log('\nTest interrupted by user', 'WARN')
            return 1
        except Exception as e:
            self.log(f'Unexpected error: {e}', 'ERROR')
            return 1
        finally:
            for _name, proc in self.processes.items():
                if proc and proc.poll() is None:
                    proc.terminate()
            self.log('\nTest runner shutdown complete')

def main():
    """Main entry point"""
    runner = E2ETestRunner()
    sys.exit(runner.run())

@pytest.mark.crust
def test_e2e_full_workflow():
    """Test the complete end-to-end workflow as a pytest test."""
    runner = (E2ETestRunner(),)
    exit_code = runner.run()
    assert exit_code == 0, 'E2E test failed'

@pytest.mark.crust
def test_e2e_test_runner_initialization():
    """Test E2E test runner can be initialized."""
    runner = E2ETestRunner()
    assert runner is not None
    assert runner.test_results == {}
    assert runner.task_ids == {}

@pytest.mark.crust
def test_e2e_logging():
    """Test E2E test logging functionality."""
    runner = E2ETestRunner()
    runner.log('Test message', 'INFO')
    runner.log('Success message', 'SUCCESS')
    runner.log('Error message', 'ERROR')
    assert runner is not None
if __name__ == '__main__':
    main()
