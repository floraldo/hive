"""Architecture validation tests to enforce the Golden Rules of Imports.

This module implements the "Golden Test" for architectural gravity - it validates
that our import rules are followed throughout the codebase and prevents violations
from being introduced in the future.

Golden Rules:
1. All *.py files that contain business logic MUST use ABSOLUTE imports for internal dependencies
2. __init__.py files are the ONLY exception - they MAY use relative imports to expose their own sub-package
3. All external scripts MUST be run as modules via Poetry with proper Python path setup
"""

import ast
import os
from pathlib import Path
from typing import List, Tuple
import pytest


class ImportValidator:
    """Validates import patterns according to our architectural rules."""

    def __init__(self, src_root: str = "src"):
        self.src_root = Path(src_root)
        self.violations = []

    def find_relative_import_violations(self) -> List[Tuple[str, int, str]]:
        """Find all violations of the no-relative-imports rule.

        Returns list of (file_path, line_number, violation_text) tuples.
        """
        violations = []

        # Walk all Python files in the EcoSystemiser package
        ecosystemiser_path = self.src_root / "EcoSystemiser"
        if not ecosystemiser_path.exists():
            return violations

        for py_file in ecosystemiser_path.rglob("*.py"):
            # Skip __init__.py files - they are allowed to use relative imports
            if py_file.name == "__init__.py":
                continue

            violations.extend(self._check_file_for_relative_imports(py_file))

        return violations

    def _check_file_for_relative_imports(self, file_path: Path) -> List[Tuple[str, int, str]]:
        """Check a single file for relative import violations."""
        violations = []

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            tree = ast.parse(content)

            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    if node.level > 0:  # Relative import detected
                        line_num = getattr(node, 'lineno', 0)

                        # Get the actual line content for context
                        lines = content.splitlines()
                        if 0 < line_num <= len(lines):
                            line_content = lines[line_num - 1].strip()
                        else:
                            line_content = f"from {'.' * node.level}{node.module or ''} import ..."

                        violations.append((
                            str(file_path.relative_to(self.src_root)),
                            line_num,
                            line_content
                        ))

        except (SyntaxError, UnicodeDecodeError) as e:
            # Log the error but don't fail the test for unparseable files
            print(f"Warning: Could not parse {file_path}: {e}")

        return violations

    def find_init_absolute_import_violations(self) -> List[Tuple[str, int, str]]:
        """Find __init__.py files that use incorrect absolute imports for their own subdirectories.

        __init__.py files should use relative imports for modules in their own directory.
        """
        violations = []

        ecosystemiser_path = self.src_root / "EcoSystemiser"
        if not ecosystemiser_path.exists():
            return violations

        for init_file in ecosystemiser_path.rglob("__init__.py"):
            violations.extend(self._check_init_file_imports(init_file))

        return violations

    def _check_init_file_imports(self, file_path: Path) -> List[Tuple[str, int, str]]:
        """Check an __init__.py file for incorrect absolute imports."""
        violations = []

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            tree = ast.parse(content)

            # Get the package path this __init__.py represents
            package_parts = file_path.parent.relative_to(self.src_root).parts
            package_prefix = ".".join(package_parts)

            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    if node.level == 0:  # Absolute import
                        # Check if it's importing from its own subdirectory
                        if node.module.startswith(package_prefix + "."):
                            # This should probably be a relative import
                            relative_part = node.module[len(package_prefix) + 1:]

                            # Check if the imported module exists as a sibling
                            sibling_path = file_path.parent / (relative_part.replace('.', '/') + '.py')
                            sibling_dir = file_path.parent / relative_part.replace('.', '/')

                            if sibling_path.exists() or (sibling_dir.exists() and sibling_dir.is_dir()):
                                line_num = getattr(node, 'lineno', 0)
                                lines = content.splitlines()
                                if 0 < line_num <= len(lines):
                                    line_content = lines[line_num - 1].strip()
                                else:
                                    line_content = f"from {node.module} import ..."

                                violations.append((
                                    str(file_path.relative_to(self.src_root)),
                                    line_num,
                                    f"Should use relative import: {line_content}"
                                ))

        except (SyntaxError, UnicodeDecodeError) as e:
            print(f"Warning: Could not parse {file_path}: {e}")

        return violations


def test_no_relative_imports_in_business_logic():
    """Golden Test: Ensure no business logic files use relative imports.

    This test enforces Rule #1: All *.py files that contain business logic
    MUST use ABSOLUTE imports for all internal dependencies.

    Relative imports (from .module, from ..package) are FORBIDDEN in business
    logic files as they make modules location-dependent and break the ability
    to import them from external scripts.
    """
    validator = ImportValidator()
    violations = validator.find_relative_import_violations()

    if violations:
        error_msg = "❌ ARCHITECTURE VIOLATION: Found relative imports in business logic files:\\n\\n"
        for file_path, line_num, line_content in violations:
            error_msg += f"  {file_path}:{line_num} -> {line_content}\\n"

        error_msg += "\\n🔧 Fix: Replace relative imports with absolute imports from EcoSystemiser root.\\n"
        error_msg += "Example: 'from ..services.simulation' → 'from EcoSystemiser.services.simulation'\\n"

        pytest.fail(error_msg)


def test_init_files_use_relative_imports_correctly():
    """Validate that __init__.py files use relative imports for their own subdirectories.

    This test helps catch cases where __init__.py files use absolute imports
    to import from their own directory, which should use relative imports instead.
    """
    validator = ImportValidator()
    violations = validator.find_init_absolute_import_violations()

    if violations:
        error_msg = "⚠️  INIT FILE PATTERN: Found __init__.py files that might benefit from relative imports:\\n\\n"
        for file_path, line_num, line_content in violations:
            error_msg += f"  {file_path}:{line_num} -> {line_content}\\n"

        error_msg += "\\n💡 Consider: Use relative imports in __init__.py for same-directory modules.\\n"
        error_msg += "Example: 'from EcoSystemiser.services.simulation' → 'from .simulation' (in services/__init__.py)\\n"

        # This is a warning, not a hard failure
        print(error_msg)


def test_architecture_documentation():
    """Ensure this test file itself documents the architecture rules."""
    # This test validates that we have clear documentation of our rules
    assert __doc__ is not None, "Architecture rules must be documented"
    assert "Golden Rules" in __doc__, "Golden Rules must be documented"
    assert "ABSOLUTE imports" in __doc__, "Rule about absolute imports must be documented"
    assert "__init__.py" in __doc__, "Exception for __init__.py must be documented"


if __name__ == "__main__":
    # Allow running this test directly for quick validation
    print("🔍 Running architecture validation...")

    validator = ImportValidator()

    print("\\n1. Checking for relative import violations...")
    violations = validator.find_relative_import_violations()
    if violations:
        print(f"❌ Found {len(violations)} violations:")
        for file_path, line_num, line_content in violations:
            print(f"   {file_path}:{line_num} -> {line_content}")
    else:
        print("✅ No relative import violations found")

    print("\\n2. Checking __init__.py import patterns...")
    init_violations = validator.find_init_absolute_import_violations()
    if init_violations:
        print(f"💡 Found {len(init_violations)} potential improvements:")
        for file_path, line_num, line_content in init_violations:
            print(f"   {file_path}:{line_num} -> {line_content}")
    else:
        print("✅ __init__.py files look good")

    print(f"\\n🎯 Architecture validation complete.")
    if violations:
        exit(1)  # Fail if there are violations
    else:
        exit(0)  # Success