"""
Fix Generation using constrained LLM prompts.

Generates targeted code fixes for specific error types.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from hive_logging import get_logger

from .error_analyzer import ParsedError, ValidationTool

logger = get_logger(__name__)


@dataclass
class GeneratedFix:
    """A generated fix for a code error"""

    error: ParsedError
    fix_type: str  # "import", "type_annotation", "variable_definition", etc.
    original_line: str | None
    fixed_line: str
    explanation: str
    confidence: float  # 0.0-1.0
    requires_context: bool = False  # Needs surrounding code context


class FixGenerator:
    """
    Generates targeted fixes for code errors.

    Uses rule-based generation for simple fixes (imports, formatting)
    and LLM-based generation for complex fixes (logic, types).
    """

    def __init__(self) -> None:
        self.logger = logger

    def generate_fix(self, error: ParsedError, file_content: str, context_lines: int = 5) -> GeneratedFix | None:
        """
        Generate a fix for the given error.

        Args:
            error: Parsed error to fix
            file_content: Full content of the file
            context_lines: Number of lines before/after error for context

        Returns:
            GeneratedFix if fixable, None otherwise
        """
        self.logger.info(f"Generating fix for {error.error_code}: {error.error_message}")

        # Route to appropriate fix generator
        if error.tool == ValidationTool.RUFF:
            return self._generate_ruff_fix(error, file_content, context_lines)
        elif error.tool == ValidationTool.PYTEST:
            return self._generate_pytest_fix(error, file_content)
        elif error.tool == ValidationTool.MYPY:
            return self._generate_mypy_fix(error, file_content, context_lines)
        else:
            self.logger.warning(f"No fix generator for tool: {error.tool}")
            return None

    def _generate_ruff_fix(self, error: ParsedError, file_content: str, context_lines: int) -> GeneratedFix | None:
        """Generate fix for ruff errors"""

        # F821: Undefined name - likely missing import
        if error.error_code == "F821":
            return self._fix_missing_import(error, file_content)

        # F401: Unused import - remove it
        if error.error_code == "F401":
            return self._fix_unused_import(error, file_content)

        # I001: Unsorted imports - sort them
        if error.error_code == "I001":
            return self._fix_unsorted_imports(error, file_content)

        # E/W codes: Formatting issues (delegated to ruff --fix)
        if error.error_code.startswith(("E", "W")):
            return None  # Let ruff --fix handle these

        return None

    def _fix_missing_import(self, error: ParsedError, file_content: str) -> GeneratedFix | None:
        """
        Fix F821: undefined name by adding appropriate import.

        Example: 'os' is undefined -> add 'import os'
        """
        # Extract the undefined name from error message
        match = re.search(r"undefined name '(.+?)'", error.error_message)
        if not match:
            return None

        undefined_name = match.group(1)

        # Common standard library mappings
        stdlib_imports = {
            "os": "import os",
            "sys": "import sys",
            "re": "import re",
            "json": "import json",
            "datetime": "from datetime import datetime",
            "Path": "from pathlib import Path",
            "List": "from typing import List",
            "Dict": "from typing import Dict",
            "Optional": "from typing import Optional",
            "Any": "from typing import Any",
        }

        # Check if it's a known standard library import
        import_statement = stdlib_imports.get(undefined_name)
        if not import_statement:
            # Generic import for unknown names
            import_statement = f"import {undefined_name}"

        return GeneratedFix(
            error=error,
            fix_type="add_import",
            original_line=None,
            fixed_line=import_statement,
            explanation=f"Add missing import for '{undefined_name}'",
            confidence=0.9 if undefined_name in stdlib_imports else 0.6,
        )

    def _fix_unused_import(self, error: ParsedError, file_content: str) -> GeneratedFix | None:
        """
        Fix F401: unused import by removing it.

        Example: 'import os' is unused -> remove line
        """
        if error.line_number is None:
            return None

        lines = file_content.split("\n")
        if error.line_number > len(lines):
            return None

        original_line = lines[error.line_number - 1]

        return GeneratedFix(
            error=error,
            fix_type="remove_import",
            original_line=original_line,
            fixed_line="",  # Remove the line
            explanation=f"Remove unused import: {original_line.strip()}",
            confidence=0.95,  # High confidence for unused imports
        )

    def _fix_unsorted_imports(self, error: ParsedError, file_content: str) -> GeneratedFix | None:
        """
        Fix I001: unsorted imports.

        Note: This is complex - better to let ruff --fix handle it
        """
        return None  # Delegate to ruff --fix

    def _generate_pytest_fix(self, error: ParsedError, file_content: str) -> GeneratedFix | None:
        """Generate fix for pytest errors"""

        # ImportError/ModuleNotFoundError - add missing import
        if error.error_code in ["ImportError", "ModuleNotFoundError"]:
            # Extract module name from error message
            match = re.search(r"No module named '(.+?)'", error.error_message)
            if match:
                module_name = match.group(1)
                return GeneratedFix(
                    error=error,
                    fix_type="add_import",
                    original_line=None,
                    fixed_line=f"import {module_name}",
                    explanation=f"Add missing module import: {module_name}",
                    confidence=0.8,
                )

        # Test failures are not auto-fixable (they indicate code bugs)
        return None

    def _generate_mypy_fix(self, error: ParsedError, file_content: str, context_lines: int) -> GeneratedFix | None:
        """Generate fix for mypy type errors"""

        # For now, we'll skip mypy fixes as they're more complex
        # Future enhancement: add type annotations for simple cases
        return None

    def batch_generate_fixes(self, errors: list[ParsedError], file_content: str) -> list[GeneratedFix]:
        """
        Generate fixes for multiple errors at once.

        Args:
            errors: List of errors to fix
            file_content: Full file content

        Returns:
            List of generated fixes
        """
        fixes = []
        for error in errors:
            if not error.is_fixable:
                continue

            fix = self.generate_fix(error, file_content)
            if fix:
                fixes.append(fix)

        self.logger.info(f"Generated {len(fixes)} fixes for {len(errors)} errors")
        return fixes

    def prioritize_fixes(self, fixes: list[GeneratedFix]) -> list[GeneratedFix]:
        """
        Prioritize fixes by confidence and error severity.

        Returns fixes sorted by priority (highest first)
        """
        # Sort by confidence (desc) then by error severity
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}

        sorted_fixes = sorted(
            fixes,
            key=lambda f: (severity_order.get(f.error.severity.value, 99), -f.confidence),
        )

        return sorted_fixes
