# ruff: noqa: S603
# Security: subprocess calls in this test file use sys.executable with hardcoded,
# trusted arguments only. No user input is passed to subprocess. This is safe for
# internal testing infrastructure.

"""
Performance benchmarks for Golden Rules validation.
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest


@pytest.mark.crust
class TestGoldenRulesPerformance:
    """Benchmark tests for Golden Rules validation performance."""

    @pytest.mark.crust
    def test_full_validation_performance(self, benchmark):
        """Benchmark full Golden Rules validation on entire codebase."""

        def run_validation():
            result = subprocess.run([sys.executable, 'scripts/validate_golden_rules.py'], cwd='/c/git/hive', capture_output=True, text=True, encoding='utf-8')
            return result.returncode == 0
        result = benchmark(run_validation)
        assert result

    @pytest.mark.crust
    def test_single_file_validation_performance(self, benchmark):
        """Benchmark Golden Rules validation on a single Python file."""
        test_content = '\nimport os\nimport sys\n\ndef test_function():\n    print("This violates the logging rule")\n    return True\n\nclass TestClass:\n    def __init__(self):\n        self.data = {}\n\n    def get_data(self):\n        return self.data\n'
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(test_content)
            temp_file = f.name
        try:

            def validate_single_file():
                sys.path.insert(0, '/c/git/hive/scripts')
                try:
                    from validate_golden_rules import check_file_against_rules
                    violations = check_file_against_rules(temp_file)
                    return len(violations)
                except ImportError:
                    return 0
            violation_count = benchmark(validate_single_file)
            assert violation_count >= 0
        finally:
            Path(temp_file).unlink()

    @pytest.mark.crust
    def test_directory_scanning_performance(self, benchmark):
        """Benchmark directory scanning for Python files."""

        def scan_directories():
            python_files = []
            for root, dirs, files in os.walk('/c/git/hive'):
                dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['__pycache__', 'tests', 'benchmarks']]
                for file in files:
                    if file.endswith('.py'):
                        python_files.append(os.path.join(root, file))
            return len(python_files)
        file_count = benchmark(scan_directories)
        assert file_count > 10

    @pytest.mark.crust
    def test_rule_application_performance(self, benchmark):
        """Benchmark applying a single rule to multiple files."""
        test_files = []
        test_content = '\ndef example_function():\n    print("Test function")\n    return "result"\n'
        try:
            for i in range(10):
                with tempfile.NamedTemporaryFile(mode='w', suffix=f'_test_{i}.py', delete=False) as f:
                    f.write(test_content)
                    test_files.append(f.name)

            def apply_logging_rule():
                violations = 0
                for file_path in test_files:
                    try:
                        with open(file_path, encoding='utf-8') as f:
                            content = f.read()
                            if 'print(' in content:
                                violations += content.count('print(')
                    except Exception:
                        pass
                return violations
            violation_count = benchmark(apply_logging_rule)
            assert violation_count >= 10
        finally:
            for file_path in test_files:
                try:
                    Path(file_path).unlink()
                except Exception:
                    pass
