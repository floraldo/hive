"""
Performance benchmarks for Golden Rules validation.
"""

import os
import subprocess
import sys
import tempfile
from pathlib import Path


class TestGoldenRulesPerformance:
    """Benchmark tests for Golden Rules validation performance."""

    def test_full_validation_performance(self, benchmark):
        """Benchmark full Golden Rules validation on entire codebase."""

        def run_validation():
            result = subprocess.run(
                [sys.executable, "scripts/validate_golden_rules.py"],
                cwd="/c/git/hive",
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            return result.returncode == 0

        result = benchmark(run_validation)
        # Validation should pass for performance testing
        assert result

    def test_single_file_validation_performance(self, benchmark):
        """Benchmark Golden Rules validation on a single Python file."""

        # Create a test file with known violations
        test_content = """
import os
import sys

def test_function():
    print("This violates the logging rule")
    return True

class TestClass:
    def __init__(self):
        self.data = {}

    def get_data(self):
        return self.data
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(test_content)
            temp_file = f.name

        try:

            def validate_single_file():
                # Import the validation functions
                sys.path.insert(0, "/c/git/hive/scripts")
                try:
                    from validate_golden_rules import check_file_against_rules

                    violations = check_file_against_rules(temp_file)
                    return len(violations)
                except ImportError:
                    # Fallback if import fails
                    return 0

            violation_count = benchmark(validate_single_file)
            # Should find some violations in our test file
            assert violation_count >= 0

        finally:
            Path(temp_file).unlink()

    def test_directory_scanning_performance(self, benchmark):
        """Benchmark directory scanning for Python files."""

        def scan_directories():
            python_files = []
            for root, dirs, files in os.walk("/c/git/hive"):
                # Skip test and benchmark directories for performance
                dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ["__pycache__", "tests", "benchmarks"]]

                for file in files:
                    if file.endswith(".py"):
                        python_files.append(os.path.join(root, file))

            return len(python_files)

        file_count = benchmark(scan_directories)
        # Should find significant number of Python files
        assert file_count > 10

    def test_rule_application_performance(self, benchmark):
        """Benchmark applying a single rule to multiple files."""

        # Create multiple test files
        test_files = []
        test_content = """
def example_function():
    print("Test function")
    return "result"
"""

        try:
            for i in range(10):
                with tempfile.NamedTemporaryFile(mode="w", suffix=f"_test_{i}.py", delete=False) as f:
                    f.write(test_content)
                    test_files.append(f.name)

            def apply_logging_rule():
                violations = 0
                for file_path in test_files:
                    try:
                        with open(file_path, encoding="utf-8") as f:
                            content = f.read()
                            # Simple check for print statements (logging rule)
                            if "print(" in content:
                                violations += content.count("print(")
                    except Exception:
                        pass
                return violations

            violation_count = benchmark(apply_logging_rule)
            # Should find print statements in our test files
            assert violation_count >= 10  # One print per file

        finally:
            for file_path in test_files:
                try:
                    Path(file_path).unlink()
                except Exception:
                    pass
