"""Error Analysis for validation tool output.

Parses output from pytest, ruff, mypy and extracts structured error information.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from hive_logging import get_logger
from hive_performance import track_request

logger = get_logger(__name__)


class ValidationTool(str, Enum):
    """Validation tool types"""

    PYTEST = "pytest"
    RUFF = "ruff"
    MYPY = "mypy"
    SYNTAX = "syntax"


class ErrorSeverity(str, Enum):
    """Error severity levels"""

    CRITICAL = "critical"  # Syntax errors, import failures
    HIGH = "high"  # Type errors, undefined variables
    MEDIUM = "medium"  # Style violations, complexity
    LOW = "low"  # Formatting, minor issues


@dataclass
class ParsedError:
    """Structured error information"""

    tool: ValidationTool
    file_path: str
    line_number: int | None
    column: int | None
    error_code: str
    error_message: str
    severity: ErrorSeverity
    full_context: str  # Original error text
    is_fixable: bool = True  # Can this error be auto-fixed?

    def to_dict(self) -> dict:
        """Convert to dictionary for logging/storage"""
        return {
            "tool": self.tool.value,
            "file": self.file_path,
            "line": self.line_number,
            "column": self.column,
            "code": self.error_code,
            "message": self.error_message,
            "severity": self.severity.value,
            "fixable": self.is_fixable,
        }


class ErrorAnalyzer:
    """Analyzes validation tool output and extracts structured errors.

    Supports:
    - pytest: Test failures and collection errors
    - ruff: Linting violations
    - mypy: Type checking errors
    - python -m py_compile: Syntax errors
    """

    def __init__(self) -> None:
        self.logger = logger

    @track_request("error_analysis_ruff", labels={"component": "error_analyzer", "tool": "ruff"})
    def parse_ruff_output(self, output: str) -> list[ParsedError]:
        """Parse ruff linting output.

        Format: file.py:10:5: F821 undefined name 'os'
        """
        errors = []
        pattern = r"^(.+?):(\d+):(\d+):\s+([A-Z]\d+)\s+(.+)$"

        for line in output.strip().split("\n"):
            line = line.strip()
            if not line:
                continue

            match = re.match(pattern, line)
            if match:
                file_path, line_num, col, code, message = match.groups()

                # Determine severity and fixability
                severity = self._determine_ruff_severity(code)
                is_fixable = self._is_ruff_fixable(code)

                errors.append(
                    ParsedError(
                        tool=ValidationTool.RUFF,
                        file_path=file_path,
                        line_number=int(line_num),
                        column=int(col),
                        error_code=code,
                        error_message=message,
                        severity=severity,
                        full_context=line,
                        is_fixable=is_fixable,
                    ),
                )

        self.logger.info(f"Parsed {len(errors)} ruff errors")
        return errors

    def parse_pytest_output(self, output: str) -> list[ParsedError]:
        """Parse pytest output.

        Looks for:
        - FAILED tests/test_file.py::test_name
        - ImportError, ModuleNotFoundError
        - AssertionError with context
        """
        errors = []

        # Pattern for failed tests
        failed_pattern = r"FAILED (.+?)::(.+?) - (.+)"

        # Pattern for import errors
        import_pattern = r"(ImportError|ModuleNotFoundError): (.+)"

        for line in output.strip().split("\n"):
            line = line.strip()

            # Check for failed test
            match = re.search(failed_pattern, line)
            if match:
                file_path, test_name, error_msg = match.groups()
                errors.append(
                    ParsedError(
                        tool=ValidationTool.PYTEST,
                        file_path=file_path,
                        line_number=None,  # pytest doesn't always provide line
                        column=None,
                        error_code="TEST_FAILURE",
                        error_message=f"{test_name}: {error_msg}",
                        severity=ErrorSeverity.HIGH,
                        full_context=line,
                        is_fixable=False,  # Test failures need code fixes, not test fixes
                    ),
                )
                continue

            # Check for import error
            match = re.search(import_pattern, line)
            if match:
                error_type, module_name = match.groups()
                errors.append(
                    ParsedError(
                        tool=ValidationTool.PYTEST,
                        file_path="unknown",  # Import errors may not specify file
                        line_number=None,
                        column=None,
                        error_code=error_type,
                        error_message=module_name,
                        severity=ErrorSeverity.CRITICAL,
                        full_context=line,
                        is_fixable=True,  # Can add missing imports
                    ),
                )

        self.logger.info(f"Parsed {len(errors)} pytest errors")
        return errors

    def parse_mypy_output(self, output: str) -> list[ParsedError]:
        """Parse mypy type checking output.

        Format: file.py:10: error: Incompatible types [assignment]
        """
        errors = []
        pattern = r"^(.+?):(\d+):\s+(error|note):\s+(.+?)(?:\s+\[(.+?)\])?$"

        for line in output.strip().split("\n"):
            line = line.strip()
            if not line:
                continue

            match = re.match(pattern, line)
            if match:
                file_path, line_num, level, message, code = match.groups()

                # Skip notes, focus on errors
                if level == "note":
                    continue

                severity = ErrorSeverity.HIGH if level == "error" else ErrorSeverity.MEDIUM
                error_code = code if code else "TYPE_ERROR"

                errors.append(
                    ParsedError(
                        tool=ValidationTool.MYPY,
                        file_path=file_path,
                        line_number=int(line_num),
                        column=None,
                        error_code=error_code,
                        error_message=message,
                        severity=severity,
                        full_context=line,
                        is_fixable=self._is_mypy_fixable(error_code),
                    ),
                )

        self.logger.info(f"Parsed {len(errors)} mypy errors")
        return errors

    def parse_syntax_error(self, output: str) -> list[ParsedError]:
        """Parse Python syntax error output.

        Format: SyntaxError: invalid syntax (file.py, line 10)
        """
        errors = []
        pattern = r"SyntaxError: (.+?) \((.+?), line (\d+)\)"

        for line in output.strip().split("\n"):
            match = re.search(pattern, line)
            if match:
                message, file_path, line_num = match.groups()
                errors.append(
                    ParsedError(
                        tool=ValidationTool.SYNTAX,
                        file_path=file_path,
                        line_number=int(line_num),
                        column=None,
                        error_code="SYNTAX_ERROR",
                        error_message=message,
                        severity=ErrorSeverity.CRITICAL,
                        full_context=line,
                        is_fixable=False,  # Syntax errors are complex
                    ),
                )

        self.logger.info(f"Parsed {len(errors)} syntax errors")
        return errors

    def _determine_ruff_severity(self, code: str) -> ErrorSeverity:
        """Determine severity based on ruff error code"""
        # F-codes (pyflakes): undefined names, imports
        if code.startswith("F"):
            if code in ["F821", "F822", "F401"]:  # Undefined name, unused import
                return ErrorSeverity.HIGH
            return ErrorSeverity.MEDIUM

        # E-codes (pycodestyle errors): formatting
        if code.startswith("E"):
            return ErrorSeverity.LOW

        # W-codes (pycodestyle warnings)
        if code.startswith("W"):
            return ErrorSeverity.LOW

        # S-codes (security)
        if code.startswith("S"):
            return ErrorSeverity.HIGH

        return ErrorSeverity.MEDIUM

    def _is_ruff_fixable(self, code: str) -> bool:
        """Determine if ruff error can be auto-fixed"""
        # Fixable: missing imports, unused imports, formatting
        fixable_codes = [
            "F401",  # Unused import
            "F821",  # Undefined name (can add import)
            "E",  # All formatting issues
            "W",  # All warnings (mostly formatting)
            "I001",  # Unsorted imports
        ]

        for fixable in fixable_codes:
            if code.startswith(fixable):
                return True

        return False

    def _is_mypy_fixable(self, code: str) -> bool:
        """Determine if mypy error can be auto-fixed"""
        # Fixable: missing imports, simple type annotations
        fixable_codes = [
            "import",  # Import errors
            "name-defined",  # Undefined names
        ]

        for fixable in fixable_codes:
            if fixable in code.lower():
                return True

        return False

    @track_request("error_categorization", labels={"component": "error_analyzer"})
    def categorize_errors(self, errors: list[ParsedError]) -> dict[str, list[ParsedError]]:
        """Categorize errors by type for prioritized fixing.

        Returns:
            Dictionary with keys: critical, high, medium, low

        """
        categorized = {"critical": [], "high": [], "medium": [], "low": []}

        for error in errors:
            categorized[error.severity.value].append(error)

        self.logger.info(
            f"Categorized {len(errors)} errors: "
            f"{len(categorized['critical'])} critical, "
            f"{len(categorized['high'])} high, "
            f"{len(categorized['medium'])} medium, "
            f"{len(categorized['low'])} low",
        )

        return categorized

    def get_fixable_errors(self, errors: list[ParsedError]) -> list[ParsedError]:
        """Filter to only fixable errors"""
        fixable = [e for e in errors if e.is_fixable]
        self.logger.info(f"{len(fixable)}/{len(errors)} errors are auto-fixable")
        return fixable
