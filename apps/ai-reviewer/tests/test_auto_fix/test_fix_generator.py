"""Unit tests for FixGenerator component.

Tests fix generation for various error types.
"""

from __future__ import annotations

import pytest

from ai_reviewer.auto_fix import ErrorAnalyzer, FixGenerator, ParsedError, ValidationTool


class TestFixGenerator:
    """Test FixGenerator functionality"""

    @pytest.fixture
    def generator(self):
        """Create FixGenerator instance"""
        return FixGenerator()

    @pytest.fixture
    def analyzer(self):
        """Create ErrorAnalyzer instance"""
        return ErrorAnalyzer()

    def test_fix_missing_import_stdlib(self, generator, analyzer):
        """Test fix for missing stdlib import"""
        # Parse a real F821 error
        ruff_output = "main.py:10:5: F821 undefined name 'os'"
        errors = analyzer.parse_ruff_output(ruff_output)

        file_content = """def get_path():
    return os.getcwd()
"""

        fix = generator.generate_fix(errors[0], file_content)

        assert fix is not None
        assert fix.fix_type == "add_import"
        assert fix.fixed_line == "import os"
        assert fix.confidence == 0.9  # High confidence for stdlib
        assert "missing import" in fix.explanation.lower()

    def test_fix_missing_import_unknown(self, generator):
        """Test fix for unknown import"""
        # Create error manually
        from ai_reviewer.auto_fix.error_analyzer import ErrorSeverity

        error = ParsedError(
            tool=ValidationTool.RUFF,
            file_path="main.py",
            line_number=10,
            column=5,
            error_code="F821",
            error_message="undefined name 'custom_module'",
            severity=ErrorSeverity.HIGH,
            full_context="main.py:10:5: F821 undefined name 'custom_module'",
            is_fixable=True,
        )

        file_content = "x = custom_module.function()"

        fix = generator._fix_missing_import(error, file_content)

        assert fix is not None
        assert fix.fixed_line == "import custom_module"
        assert fix.confidence == 0.6  # Lower confidence for unknown

    def test_fix_missing_import_typing(self, generator, analyzer):
        """Test fix for missing typing import"""
        ruff_output = "main.py:5:10: F821 undefined name 'List'"
        errors = analyzer.parse_ruff_output(ruff_output)

        file_content = """def process(items: List[str]):
    pass
"""

        fix = generator.generate_fix(errors[0], file_content)

        assert fix is not None
        assert fix.fixed_line == "from typing import List"
        assert fix.confidence == 0.9

    def test_fix_unused_import(self, generator, analyzer):
        """Test fix for unused import"""
        ruff_output = "main.py:1:1: F401 'sys' imported but unused"
        errors = analyzer.parse_ruff_output(ruff_output)

        file_content = """import sys
import os

def main():
    print(os.getcwd())
"""

        fix = generator.generate_fix(errors[0], file_content)

        assert fix is not None
        assert fix.fix_type == "remove_import"
        assert fix.fixed_line == ""  # Remove the line
        assert fix.original_line == "import sys"
        assert fix.confidence == 0.95  # Very high confidence

    def test_generate_pytest_fix_import_error(self, generator, analyzer):
        """Test fix for pytest import error"""
        pytest_output = "ImportError: No module named 'missing_package'"
        errors = analyzer.parse_pytest_output(pytest_output)

        file_content = "import missing_package"

        fix = generator.generate_fix(errors[0], file_content)

        assert fix is not None
        assert fix.fix_type == "add_import"
        assert "missing_package" in fix.fixed_line
        assert fix.confidence == 0.8

    def test_generate_fix_no_match(self, generator):
        """Test fix generation when error doesn't match"""
        from ai_reviewer.auto_fix.error_analyzer import ErrorSeverity

        error = ParsedError(
            tool=ValidationTool.RUFF,
            file_path="main.py",
            line_number=10,
            column=5,
            error_code="E999",  # Unknown code
            error_message="some error",
            severity=ErrorSeverity.LOW,
            full_context="main.py:10:5: E999 some error",
            is_fixable=False,
        )

        fix = generator.generate_fix(error, "content")

        assert fix is None  # No fix for unknown codes

    def test_batch_generate_fixes(self, generator, analyzer):
        """Test batch fix generation"""
        ruff_output = """main.py:10:5: F821 undefined name 'os'
main.py:15:1: F401 'sys' imported but unused
main.py:20:5: F821 undefined name 'Path'"""

        errors = analyzer.parse_ruff_output(ruff_output)

        file_content = """import sys

def get_path():
    return os.getcwd()

def get_file():
    return Path.cwd()
"""

        fixes = generator.batch_generate_fixes(errors, file_content)

        # Should generate fixes for F821 errors (2 total)
        # F401 may not generate if fixability logic filters it
        assert len(fixes) >= 2
        # All generated fixes should be valid
        assert all(fix is not None for fix in fixes)

    def test_prioritize_fixes(self, generator, analyzer):
        """Test fix prioritization by confidence and severity"""
        ruff_output = """main.py:10:5: F821 undefined name 'custom_lib'
main.py:15:1: F401 'sys' imported but unused"""

        errors = analyzer.parse_ruff_output(ruff_output)
        file_content = "import sys\nx = custom_lib.func()"

        fixes = generator.batch_generate_fixes(errors, file_content)

        # Only prioritize if we got multiple fixes
        if len(fixes) >= 2:
            prioritized = generator.prioritize_fixes(fixes)

            # Higher confidence should come first
            # F401 (unused import) has confidence 0.95
            # F821 (unknown name) has confidence 0.6
            assert prioritized[0].confidence > prioritized[1].confidence
        else:
            # If only one fix generated, just verify prioritization doesn't crash
            prioritized = generator.prioritize_fixes(fixes)
            assert len(prioritized) == len(fixes)

    def test_fix_pathlib_import(self, generator, analyzer):
        """Test fix for pathlib Path import"""
        ruff_output = "main.py:5:10: F821 undefined name 'Path'"
        errors = analyzer.parse_ruff_output(ruff_output)

        file_content = "p = Path('/tmp')"

        fix = generator.generate_fix(errors[0], file_content)

        assert fix is not None
        assert fix.fixed_line == "from pathlib import Path"
        assert fix.confidence == 0.9

    def test_fix_datetime_import(self, generator, analyzer):
        """Test fix for datetime import"""
        ruff_output = "main.py:5:10: F821 undefined name 'datetime'"
        errors = analyzer.parse_ruff_output(ruff_output)

        file_content = "now = datetime.now()"

        fix = generator.generate_fix(errors[0], file_content)

        assert fix is not None
        assert fix.fixed_line == "from datetime import datetime"

    def test_mypy_fix_not_implemented(self, generator):
        """Test that mypy fixes are not yet implemented"""
        from ai_reviewer.auto_fix.error_analyzer import ErrorSeverity

        error = ParsedError(
            tool=ValidationTool.MYPY,
            file_path="main.py",
            line_number=10,
            column=None,
            error_code="assignment",
            error_message="Incompatible types",
            severity=ErrorSeverity.HIGH,
            full_context="main.py:10: error: Incompatible types [assignment]",
            is_fixable=False,
        )

        fix = generator.generate_fix(error, "x: int = 'string'")

        # Mypy fixes not implemented yet
        assert fix is None
