"""Unit tests for ErrorAnalyzer component.

Tests error parsing from pytest, ruff, mypy output.
"""

from __future__ import annotations

from ai_reviewer.auto_fix import ErrorAnalyzer, ErrorSeverity, ValidationTool


class TestErrorAnalyzer:
    """Test ErrorAnalyzer functionality"""

    def test_parse_ruff_output_basic(self):
        """Test parsing basic ruff output"""
        analyzer = ErrorAnalyzer()
        output = """src/main.py:10:5: F821 undefined name 'os'
src/utils.py:25:1: F401 'sys' imported but unused"""

        errors = analyzer.parse_ruff_output(output)

        assert len(errors) == 2

        # First error
        assert errors[0].tool == ValidationTool.RUFF
        assert errors[0].file_path == "src/main.py"
        assert errors[0].line_number == 10
        assert errors[0].column == 5
        assert errors[0].error_code == "F821"
        assert "undefined name 'os'" in errors[0].error_message
        assert errors[0].severity == ErrorSeverity.HIGH
        assert errors[0].is_fixable is True

        # Second error
        assert errors[1].error_code == "F401"
        assert errors[1].is_fixable is True

    def test_parse_ruff_output_empty(self):
        """Test parsing empty ruff output"""
        analyzer = ErrorAnalyzer()
        errors = analyzer.parse_ruff_output("")

        assert len(errors) == 0

    def test_parse_pytest_output_failed_test(self):
        """Test parsing pytest failed test output"""
        analyzer = ErrorAnalyzer()
        output = """FAILED tests/test_main.py::test_function - AssertionError: expected True"""

        errors = analyzer.parse_pytest_output(output)

        assert len(errors) == 1
        assert errors[0].tool == ValidationTool.PYTEST
        assert errors[0].error_code == "TEST_FAILURE"
        assert "test_function" in errors[0].error_message
        assert errors[0].severity == ErrorSeverity.HIGH
        assert errors[0].is_fixable is False  # Test failures not auto-fixable

    def test_parse_pytest_output_import_error(self):
        """Test parsing pytest import error"""
        analyzer = ErrorAnalyzer()
        output = """ImportError: No module named 'missing_module'"""

        errors = analyzer.parse_pytest_output(output)

        assert len(errors) == 1
        assert errors[0].error_code == "ImportError"
        assert "missing_module" in errors[0].error_message
        assert errors[0].severity == ErrorSeverity.CRITICAL
        assert errors[0].is_fixable is True  # Import errors can be fixed

    def test_parse_mypy_output_basic(self):
        """Test parsing mypy type errors"""
        analyzer = ErrorAnalyzer()
        output = """src/main.py:15: error: Incompatible types [assignment]
src/utils.py:20: error: Name 'foo' is not defined [name-defined]"""

        errors = analyzer.parse_mypy_output(output)

        assert len(errors) == 2
        assert errors[0].tool == ValidationTool.MYPY
        assert errors[0].error_code == "assignment"
        assert errors[0].severity == ErrorSeverity.HIGH

    def test_parse_syntax_error(self):
        """Test parsing syntax errors"""
        analyzer = ErrorAnalyzer()
        output = """SyntaxError: invalid syntax (main.py, line 42)"""

        errors = analyzer.parse_syntax_error(output)

        assert len(errors) == 1
        assert errors[0].tool == ValidationTool.SYNTAX
        assert errors[0].error_code == "SYNTAX_ERROR"
        assert errors[0].line_number == 42
        assert errors[0].severity == ErrorSeverity.CRITICAL
        assert errors[0].is_fixable is False  # Syntax errors complex

    def test_categorize_errors(self):
        """Test error categorization by severity"""
        analyzer = ErrorAnalyzer()
        ruff_output = """src/main.py:10:5: F821 undefined name 'os'
src/utils.py:25:1: E501 line too long"""

        errors = analyzer.parse_ruff_output(ruff_output)
        categorized = analyzer.categorize_errors(errors)

        assert "critical" in categorized
        assert "high" in categorized
        assert "medium" in categorized
        assert "low" in categorized

        # F821 is HIGH severity
        assert len(categorized["high"]) >= 1
        # E501 is LOW severity
        assert len(categorized["low"]) >= 1

    def test_get_fixable_errors(self):
        """Test filtering to fixable errors only"""
        analyzer = ErrorAnalyzer()

        # Mix of fixable and non-fixable
        pytest_output = """FAILED tests/test_main.py::test_function - AssertionError
ImportError: No module named 'foo'"""

        errors = analyzer.parse_pytest_output(pytest_output)
        fixable = analyzer.get_fixable_errors(errors)

        # Only ImportError should be fixable
        assert len(fixable) == 1
        assert fixable[0].error_code == "ImportError"

    def test_determine_ruff_severity(self):
        """Test severity determination for ruff codes"""
        analyzer = ErrorAnalyzer()

        # F-codes (undefined, imports) - HIGH
        assert analyzer._determine_ruff_severity("F821") == ErrorSeverity.HIGH
        assert analyzer._determine_ruff_severity("F401") == ErrorSeverity.HIGH

        # E-codes (formatting) - LOW
        assert analyzer._determine_ruff_severity("E501") == ErrorSeverity.LOW

        # S-codes (security) - HIGH
        assert analyzer._determine_ruff_severity("S603") == ErrorSeverity.HIGH

    def test_is_ruff_fixable(self):
        """Test fixability determination for ruff codes"""
        analyzer = ErrorAnalyzer()

        # Fixable codes
        assert analyzer._is_ruff_fixable("F401") is True  # Unused import
        assert analyzer._is_ruff_fixable("F821") is True  # Undefined name
        assert analyzer._is_ruff_fixable("E501") is True  # Formatting
        assert analyzer._is_ruff_fixable("I001") is True  # Import sorting

        # Security codes generally not auto-fixable
        # (though we mark some as fixable in current implementation)
        assert analyzer._is_ruff_fixable("S999") is False

    def test_error_to_dict(self):
        """Test ParsedError serialization"""
        analyzer = ErrorAnalyzer()
        output = "src/main.py:10:5: F821 undefined name 'os'"

        errors = analyzer.parse_ruff_output(output)
        error_dict = errors[0].to_dict()

        assert error_dict["tool"] == "ruff"
        assert error_dict["file"] == "src/main.py"
        assert error_dict["line"] == 10
        assert error_dict["column"] == 5
        assert error_dict["code"] == "F821"
        assert error_dict["severity"] == "high"
        assert error_dict["fixable"] is True
