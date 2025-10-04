"""Golden Rules compliance tests for hive-coder.
"""

from __future__ import annotations

from pathlib import Path


def get_python_files() -> list[Path]:
    """Get all Python files in hive-coder"""
    src_dir = Path(__file__).parent.parent / "src" / "hive_coder"
    return list(src_dir.rglob("*.py"))


class TestGoldenRules:
    """Test Golden Rules compliance"""

    def test_no_print_statements(self) -> None:
        """Test no print() statements (use hive_logging instead)"""
        violations = []

        for py_file in get_python_files():
            content = py_file.read_text(encoding="utf-8")
            lines = content.split("\n")

            for i, line in enumerate(lines, 1):
                # Skip comments and docstrings
                stripped = line.strip()
                if stripped.startswith("#") or '"""' in stripped or "'''" in stripped:
                    continue

                if "print(" in line:
                    violations.append(f"{py_file.name}:{i}")

        assert len(violations) == 0, f"Found print() statements: {violations}"

    def test_hive_logging_import(self) -> None:
        """Test all modules import from hive_logging"""
        violations = []

        for py_file in get_python_files():
            if py_file.name == "__init__.py":
                continue

            content = py_file.read_text(encoding="utf-8")
            if "get_logger" not in content and "logger" not in content:
                continue

            # Check if using hive_logging
            if "from hive_logging import get_logger" not in content:
                if "import logging" in content or "from logging import" in content:
                    violations.append(py_file.name)

        assert len(violations) == 0, f"Using standard logging instead of hive_logging: {violations}"

    def test_config_di_pattern(self) -> None:
        """Test configuration uses DI pattern (not global state)"""
        violations = []

        for py_file in get_python_files():
            content = py_file.read_text(encoding="utf-8")

            # Check for deprecated global config access
            if "from hive_config import get_config" in content:
                violations.append(f"{py_file.name} - uses get_config() instead of DI pattern")

        assert len(violations) == 0, f"Found deprecated config pattern: {violations}"

    def test_type_hints_present(self) -> None:
        """Test functions have type hints"""
        violations = []

        for py_file in get_python_files():
            if py_file.name == "__init__.py":
                continue

            content = py_file.read_text(encoding="utf-8")
            lines = content.split("\n")

            for i, line in enumerate(lines, 1):
                # Look for function definitions
                if line.strip().startswith("def ") and not line.strip().startswith("def __"):
                    # Check for type hints (-> or : in signature)
                    if "->" not in line and ":" not in line.split("(")[1].split(")")[0]:
                        # Skip test fixtures and simple properties
                        if "@pytest.fixture" not in lines[max(0, i - 2) : i]:
                            violations.append(f"{py_file.name}:{i}")

        # Allow some violations for simple property methods
        assert len(violations) < 5, f"Missing type hints in functions: {violations[:5]}"
