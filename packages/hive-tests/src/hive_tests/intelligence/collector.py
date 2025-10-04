"""
Pytest plugin for collecting test execution data.

Hooks into pytest execution to capture comprehensive test results
and store them in the test intelligence database.
"""
import subprocess
from datetime import datetime
from pathlib import Path

from .models import TestResult, TestRun, TestStatus, TestType
from .storage import TestIntelligenceStorage


class TestIntelligencePlugin:
    """Pytest plugin for test intelligence collection."""

    def __init__(self):
        """Initialize plugin with storage."""
        self.storage = TestIntelligenceStorage()
        self.current_run: TestRun | None = None
        self.results: list[TestResult] = []
        self.start_time: float = 0

    def pytest_sessionstart(self, session):
        """Called at the start of test session."""
        self.start_time = datetime.now().timestamp()
        self.results = []

        # Get git information if available
        git_commit = self._get_git_commit()
        git_branch = self._get_git_branch()

        # Initialize run (will update counts at end)
        self.current_run = TestRun(
            total_tests=0,
            passed=0,
            failed=0,
            errors=0,
            skipped=0,
            duration_seconds=0,
            git_commit=git_commit,
            git_branch=git_branch,
        )

    def pytest_runtest_logreport(self, report):
        """Called after each test phase (setup, call, teardown)."""
        if report.when != "call":
            # Only capture the main test execution, not setup/teardown
            return

        # Extract test information
        test_id = report.nodeid
        status = self._get_test_status(report)
        duration_ms = report.duration * 1000  # Convert to milliseconds

        # Extract package and file information
        package_name = self._extract_package_name(test_id)
        file_path = str(Path(report.fspath)) if hasattr(report, "fspath") else "unknown"
        test_type = self._infer_test_type(file_path)

        # Get error information if test failed
        error_message = None
        error_traceback = None
        if report.failed or report.outcome == "error":
            error_message = str(report.longrepr) if report.longrepr else None
            if hasattr(report.longrepr, "reprtraceback"):
                error_traceback = str(report.longrepr.reprtraceback)

        # Create test result
        result = TestResult(
            run_id=self.current_run.id,
            test_id=test_id,
            status=status,
            duration_ms=duration_ms,
            error_message=error_message,
            error_traceback=error_traceback,
            package_name=package_name,
            test_type=test_type,
            file_path=file_path,
        )

        self.results.append(result)

    def pytest_sessionfinish(self, session, exitstatus):
        """Called at the end of test session."""
        if not self.current_run:
            return

        # Calculate final statistics
        end_time = datetime.now().timestamp()
        self.current_run.duration_seconds = end_time - self.start_time

        # Count test outcomes
        status_counts = {
            TestStatus.PASSED: 0,
            TestStatus.FAILED: 0,
            TestStatus.ERROR: 0,
            TestStatus.SKIPPED: 0,
        }

        for result in self.results:
            status_counts[result.status] += 1

        self.current_run.total_tests = len(self.results)
        self.current_run.passed = status_counts[TestStatus.PASSED]
        self.current_run.failed = status_counts[TestStatus.FAILED]
        self.current_run.errors = status_counts[TestStatus.ERROR]
        self.current_run.skipped = status_counts[TestStatus.SKIPPED]

        # Save to database
        try:
            self.storage.save_test_run(self.current_run)
            for result in self.results:
                self.storage.save_test_result(result)
        except Exception as e:
            # Don't fail tests if intelligence collection fails
            print(f"Warning: Failed to save test intelligence data: {e}")

    def _get_test_status(self, report) -> TestStatus:
        """Convert pytest report outcome to TestStatus."""
        if report.passed:
            return TestStatus.PASSED
        elif report.failed:
            return TestStatus.FAILED
        elif report.skipped:
            return TestStatus.SKIPPED
        else:
            return TestStatus.ERROR

    def _extract_package_name(self, test_id: str) -> str:
        """Extract package name from test ID."""
        # Test ID format: packages/hive-ai/tests/test_core.py::TestClass::test_method
        parts = test_id.split("/")
        if len(parts) >= 2 and parts[0] == "packages":
            return parts[1]
        elif len(parts) >= 2 and parts[0] == "apps":
            return parts[1]
        return "unknown"

    def _infer_test_type(self, file_path: str) -> TestType:
        """Infer test type from file path."""
        file_path_lower = file_path.lower()

        if "/unit/" in file_path_lower or "\\unit\\" in file_path_lower:
            return TestType.UNIT
        elif "/integration/" in file_path_lower or "\\integration\\" in file_path_lower:
            return TestType.INTEGRATION
        elif "/e2e/" in file_path_lower or "\\e2e\\" in file_path_lower:
            return TestType.E2E
        elif "/smoke/" in file_path_lower or "\\smoke\\" in file_path_lower:
            return TestType.SMOKE
        elif "/benchmark/" in file_path_lower or "\\benchmark\\" in file_path_lower:
            return TestType.BENCHMARK
        elif "/resilience/" in file_path_lower or "\\resilience\\" in file_path_lower:
            return TestType.RESILIENCE
        else:
            return TestType.UNIT  # Default to unit test

    def _get_git_commit(self) -> str | None:
        """Get current git commit hash."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"], capture_output=True, text=True, timeout=2, check=False
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
        return None

    def _get_git_branch(self) -> str | None:
        """Get current git branch name."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True,
                text=True,
                timeout=2,
                check=False,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
        return None


# Plugin registration
def pytest_configure(config):
    """Register the test intelligence plugin."""
    if not config.option.collectonly:
        plugin = TestIntelligencePlugin()
        config.pluginmanager.register(plugin, "test_intelligence")


def pytest_unconfigure(config):
    """Unregister the plugin."""
    plugin = config.pluginmanager.get_plugin("test_intelligence")
    if plugin:
        config.pluginmanager.unregister(plugin)
