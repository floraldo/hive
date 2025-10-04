"""Execute E2E tests and generate reports."""

from __future__ import annotations

import json
import subprocess
from datetime import datetime
from pathlib import Path

from hive_logging import get_logger

from .models import TestResult, TestStatus

logger = get_logger(__name__)


class TestExecutor:
    """Execute pytest-based E2E tests and generate reports.

    Runs tests using pytest subprocess, parses results, and generates
    structured test reports for orchestration integration.

    Example:
        executor = TestExecutor()
        result = executor.execute_test(
            test_path="tests/e2e/test_google_login.py"
        )
        print(f"Status: {result.status}")

    """

    def __init__(self, screenshot_dir: Path | None = None) -> None:
        """Initialize test executor.

        Args:
            screenshot_dir: Directory for screenshot artifacts

        """
        self.logger = logger

        if screenshot_dir is None:
            screenshot_dir = Path("screenshots")

        self.screenshot_dir = screenshot_dir
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)

        self.logger.info(f"Test executor initialized: screenshots -> {screenshot_dir}")

    def execute_test(
        self,
        test_path: str | Path,
        headless: bool = True,
        capture_screenshots: bool = True,
        timeout: int = 120,
    ) -> TestResult:
        """Execute E2E test file.

        Args:
            test_path: Path to pytest test file
            headless: Run browser in headless mode
            capture_screenshots: Capture screenshots on failure
            timeout: Test timeout in seconds

        Returns:
            Test execution result with status and artifacts

        Example:
            result = executor.execute_test(
                test_path="tests/e2e/test_google_login.py",
                headless=True
            )

        """
        test_path = Path(test_path)
        self.logger.info(f"Executing test: {test_path}")

        if not test_path.exists():
            self.logger.error(f"Test file not found: {test_path}")
            return TestResult(
                test_path=str(test_path),
                status=TestStatus.ERROR,
                duration=0.0,
                stderr=f"Test file not found: {test_path}",
            )

        # Build pytest command
        cmd = [
            "python",
            "-m",
            "pytest",
            str(test_path),
            "-v",
            "--tb=short",
            "--json-report",
            "--json-report-file=test_report.json",
        ]

        # Environment variables for browser configuration
        env = {
            "E2E_HEADLESS": str(headless).lower(),
            "E2E_SCREENSHOT_DIR": str(self.screenshot_dir),
        }

        # Execute test
        start_time = datetime.now()

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
                env=env,
            )

            duration = (datetime.now() - start_time).total_seconds()

            # Parse pytest output
            test_result = self._parse_pytest_output(
                test_path=test_path,
                returncode=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                duration=duration,
            )

            # Collect screenshots
            if capture_screenshots:
                test_result.screenshots = self._collect_screenshots(test_path)

            self.logger.info(
                f"Test completed: {test_result.status} "
                f"({test_result.tests_passed}/{test_result.tests_run} passed)",
            )

            return test_result

        except subprocess.TimeoutExpired:
            duration = (datetime.now() - start_time).total_seconds()
            self.logger.error(f"Test timed out after {duration}s")

            return TestResult(
                test_path=str(test_path),
                status=TestStatus.ERROR,
                duration=duration,
                stderr=f"Test timed out after {timeout}s",
            )

        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            self.logger.error(f"Test execution error: {e}")

            return TestResult(
                test_path=str(test_path),
                status=TestStatus.ERROR,
                duration=duration,
                stderr=str(e),
            )

    def execute_test_suite(
        self,
        test_dir: Path,
        pattern: str = "test_*.py",
        **kwargs,
    ) -> list[TestResult]:
        """Execute all tests in directory matching pattern.

        Args:
            test_dir: Directory containing test files
            pattern: Glob pattern for test files
            **kwargs: Additional arguments for execute_test

        Returns:
            List of test results

        Example:
            results = executor.execute_test_suite(
                test_dir=Path("tests/e2e"),
                pattern="test_*.py"
            )

        """
        self.logger.info(f"Executing test suite: {test_dir}/{pattern}")

        test_files = list(test_dir.glob(pattern))

        if not test_files:
            self.logger.warning(f"No tests found matching: {test_dir}/{pattern}")
            return []

        results = []
        for test_file in test_files:
            result = self.execute_test(test_file, **kwargs)
            results.append(result)

        # Summary
        total_passed = sum(r.tests_passed for r in results)
        total_run = sum(r.tests_run for r in results)

        self.logger.info(
            f"Test suite completed: {total_passed}/{total_run} tests passed "
            f"across {len(results)} files",
        )

        return results

    def generate_report(
        self,
        result: TestResult,
        output_path: Path,
        format: str = "json",
    ) -> None:
        """Generate test report file.

        Args:
            result: Test execution result
            output_path: Path to save report
            format: Report format (json or html)

        Example:
            executor.generate_report(
                result=test_result,
                output_path=Path("reports/google_login.json"),
                format="json"
            )

        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if format == "json":
            report_data = result.model_dump(mode="json")
            output_path.write_text(
                json.dumps(report_data, indent=2, default=str),
                encoding="utf-8",
            )

        elif format == "html":
            # Simple HTML report (could be enhanced with Jinja2 template)
            html = self._generate_html_report(result)
            output_path.write_text(html, encoding="utf-8")

        else:
            msg = f"Unsupported format: {format}"
            raise ValueError(msg)

        self.logger.info(f"Report saved: {output_path}")

    def _parse_pytest_output(
        self,
        test_path: Path,
        returncode: int,
        stdout: str,
        stderr: str,
        duration: float,
    ) -> TestResult:
        """Parse pytest output to extract test results."""
        # Determine status from return code
        if returncode == 0:
            status = TestStatus.PASSED
        elif returncode == 1:
            status = TestStatus.FAILED
        else:
            status = TestStatus.ERROR

        # Parse test counts from output
        tests_run = 0
        tests_passed = 0
        tests_failed = 0
        tests_skipped = 0

        # Look for pytest summary line
        # Example: "5 passed, 2 failed, 1 skipped in 10.5s"
        import re
        summary_pattern = r"(\d+) passed|(\d+) failed|(\d+) skipped"
        matches = re.findall(summary_pattern, stdout)

        for match in matches:
            if match[0]:  # passed
                tests_passed = int(match[0])
            elif match[1]:  # failed
                tests_failed = int(match[1])
            elif match[2]:  # skipped
                tests_skipped = int(match[2])

        tests_run = tests_passed + tests_failed + tests_skipped

        return TestResult(
            test_path=str(test_path),
            status=status,
            duration=duration,
            tests_run=tests_run,
            tests_passed=tests_passed,
            tests_failed=tests_failed,
            tests_skipped=tests_skipped,
            stdout=stdout,
            stderr=stderr,
            timestamp=datetime.now(),
        )

    def _collect_screenshots(self, test_path: Path) -> list[str]:
        """Collect screenshot paths for test."""
        test_name = test_path.stem  # filename without extension

        # Look for screenshots matching test name
        screenshots = list(self.screenshot_dir.glob(f"{test_name}*.png"))

        return [str(s.resolve()) for s in screenshots]

    def _generate_html_report(self, result: TestResult) -> str:
        """Generate simple HTML test report."""
        status_color = {
            TestStatus.PASSED: "green",
            TestStatus.FAILED: "red",
            TestStatus.ERROR: "orange",
            TestStatus.SKIPPED: "gray",
        }.get(result.status, "black")

        html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Test Report: {Path(result.test_path).name}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        h1 {{ color: {status_color}; }}
        .summary {{ background: #f0f0f0; padding: 15px; border-radius: 5px; }}
        .screenshots img {{ max-width: 800px; margin: 10px; border: 1px solid #ddd; }}
    </style>
</head>
<body>
    <h1>Test Result: {result.status.value.upper()}</h1>

    <div class="summary">
        <h2>Summary</h2>
        <p><strong>Test File:</strong> {result.test_path}</p>
        <p><strong>Duration:</strong> {result.duration:.2f}s</p>
        <p><strong>Tests Run:</strong> {result.tests_run}</p>
        <p><strong>Passed:</strong> {result.tests_passed}</p>
        <p><strong>Failed:</strong> {result.tests_failed}</p>
        <p><strong>Skipped:</strong> {result.tests_skipped}</p>
        <p><strong>Timestamp:</strong> {result.timestamp.isoformat()}</p>
    </div>

    <h2>Screenshots</h2>
    <div class="screenshots">
"""

        for screenshot in result.screenshots:
            html += f'        <img src="{screenshot}" alt="Screenshot"><br>\n'

        html += f"""    </div>

    <h2>Output</h2>
    <pre>{result.stdout}</pre>

    <h2>Errors</h2>
    <pre>{result.stderr}</pre>
</body>
</html>
"""

        return html
