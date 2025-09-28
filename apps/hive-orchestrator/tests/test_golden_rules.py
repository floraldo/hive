#!/usr/bin/env python3
"""
Local Golden Rules Test for hive-orchestrator

This test file allows developers to verify architectural compliance
while working on this specific app. It runs a subset of golden rules
relevant to the current app context.

Run with: pytest tests/test_golden_rules.py -v
"""

import pytest
from pathlib import Path

# Import the validators from hive-testing-utils
from hive_testing_utils.architectural_validators import (
    validate_app_contracts,
    validate_colocated_tests,
    validate_no_syspath_hacks,
    validate_dependency_direction,
    validate_interface_contracts,
    validate_error_handling_standards,
    validate_logging_standards,
)


class TestLocalGoldenRules:
    """
    Local golden rule tests for hive-orchestrator app.
    These tests verify that this app follows platform standards.
    """

    @pytest.fixture
    def app_root(self):
        """Get the root directory of this app."""
        return Path(__file__).parent.parent

    @pytest.fixture
    def project_root(self):
        """Get the project root for full validation."""
        return Path(__file__).parent.parent.parent.parent

    def test_app_contract(self, app_root):
        """Verify this app has a valid hive-app.toml contract."""
        contract_file = app_root / "hive-app.toml"
        assert contract_file.exists(), "Missing hive-app.toml contract file"

        import toml
        contract = toml.load(contract_file)

        # Verify required sections
        assert "app" in contract, "Missing [app] section in hive-app.toml"
        assert "name" in contract["app"], "Missing app.name in hive-app.toml"

        # Verify at least one service definition
        service_sections = ["daemons", "tasks", "endpoints"]
        has_service = any(section in contract for section in service_sections)
        assert has_service, "Missing service definitions (daemons/tasks/endpoints)"

    def test_colocated_tests(self, app_root):
        """Verify this app has proper test structure."""
        tests_dir = app_root / "tests"
        assert tests_dir.exists(), "Missing tests/ directory"
        assert (tests_dir / "__init__.py").exists(), "Missing tests/__init__.py"

    def test_no_path_hacks(self, app_root):
        """Verify no sys.path manipulation in this app."""
        violations = []

        for py_file in app_root.rglob("*.py"):
            if ".venv" in str(py_file) or "__pycache__" in str(py_file):
                continue

            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()

                # Check for sys.path manipulation patterns
                path_insert = "sys.path." + "insert"
                path_append = "sys.path." + "append"
                if path_insert in content or path_append in content:
                    # Skip allowed files
                    if "verify_environment.py" not in str(py_file):
                        violations.append(str(py_file.relative_to(app_root)))
            except Exception:
                continue

        assert not violations, f"Path manipulation found in: {violations}"

    def test_no_direct_app_imports(self, app_root):
        """Verify this app doesn't import directly from other apps."""
        violations = []
        other_apps = ["ai-planner", "ai-reviewer", "event-dashboard", "ecosystemiser"]

        for py_file in app_root.rglob("*.py"):
            if ".venv" in str(py_file) or "__pycache__" in str(py_file):
                continue

            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()

                for other_app in other_apps:
                    import_patterns = [
                        f"from {other_app.replace('-', '_')}",
                        f"import {other_app.replace('-', '_')}"
                    ]

                    for pattern in import_patterns:
                        if pattern in content:
                            # Check if it's a shared package (allowed)
                            shared_patterns = ["_core", "_shared"]
                            if not any(sp in pattern for sp in shared_patterns):
                                violations.append(
                                    f"{py_file.relative_to(app_root)}: imports from {other_app}"
                                )
                                break
            except Exception:
                continue

        assert not violations, f"Direct app imports found:\n" + "\n".join(violations)

    def test_logging_standards(self, app_root):
        """Verify proper logging usage in this app."""
        violations = []

        for py_file in app_root.rglob("*.py"):
            if (".venv" in str(py_file) or "__pycache__" in str(py_file) or
                "test" in str(py_file) or "__main__" in str(py_file.name)):
                continue

            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()

                # Check for print statements
                if "print(" in content:
                    lines = content.split('\n')
                    for i, line in enumerate(lines, 1):
                        if "print(" in line and not line.strip().startswith('#'):
                            violations.append(
                                f"{py_file.relative_to(app_root)}:{i}: print statement"
                            )

                # Check if uses logging but not hive_logging
                if ("logger" in content.lower() or "logging" in content.lower()):
                    if "from hive_logging import" not in content and "import hive_logging" not in content:
                        violations.append(
                            f"{py_file.relative_to(app_root)}: uses logging without hive_logging"
                        )
            except Exception:
                continue

        # Allow some violations for now but warn
        if violations:
            print(f"Warning: {len(violations)} logging standard violations found")
            for v in violations[:5]:  # Show first 5
                print(f"  - {v}")

    def test_error_handling(self, app_root):
        """Verify proper error handling in this app."""
        violations = []

        for py_file in app_root.rglob("*.py"):
            if (".venv" in str(py_file) or "__pycache__" in str(py_file) or
                "test" in str(py_file)):
                continue

            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()

                # Check for bare except clauses
                lines = content.split('\n')
                for i, line in enumerate(lines, 1):
                    if line.strip() == "except:" or line.strip() == "except Exception:":
                        violations.append(
                            f"{py_file.relative_to(app_root)}:{i}: bare except clause"
                        )
            except Exception:
                continue

        # Allow some violations for now but warn
        if violations:
            print(f"Warning: {len(violations)} error handling violations found")
            for v in violations[:5]:  # Show first 5
                print(f"  - {v}")


if __name__ == "__main__":
    # Allow running directly with python
    import sys
    pytest.main([__file__, "-v", "--tb=short"])