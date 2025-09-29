#!/usr/bin/env python3
"""
Emergency restoration script for linter-corrupted files.

The automated linters have systematically corrupted the codebase with
thousands of inappropriate trailing commas. This script restores basic syntax.
"""

import ast
import re
from pathlib import Path


def emergency_fix_file(file_path: Path) -> bool:
    """Emergency fix for critical syntax errors in a file."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        original = content

        # Remove trailing commas from import statements
        content = re.sub(r"^(\s*from __future__ import annotations),\s*$", r"\1", content, flags=re.MULTILINE)
        content = re.sub(r"^(\s*from [a-zA-Z_][^\n]*),\s*$", r"\1", content, flags=re.MULTILINE)
        content = re.sub(r"^(\s*import [a-zA-Z_][^\n]*),\s*$", r"\1", content, flags=re.MULTILINE)

        # Remove trailing commas from try/except statements
        content = re.sub(r"^(\s*try):,\s*$", r"\1:", content, flags=re.MULTILINE)
        content = re.sub(r"^(\s*except [^:]*):,\s*$", r"\1:", content, flags=re.MULTILINE)

        # Remove trailing commas from single variable assignments
        content = re.sub(r"^(\s*[a-zA-Z_][a-zA-Z0-9_]*\s*=\s*[^,\n]+),\s*$", r"\1", content, flags=re.MULTILINE)

        # Remove trailing commas from logger statements
        content = re.sub(r"^(\s*logger = get_logger\(__name__\)),\s*$", r"\1", content, flags=re.MULTILINE)

        # Remove trailing commas from pass statements
        content = re.sub(r"^(\s*pass),\s*$", r"\1", content, flags=re.MULTILINE)

        # Remove trailing commas from single-line docstrings
        content = re.sub(r'^(\s*"""[^"]*"""),\s*$', r"\1", content, flags=re.MULTILINE)

        # Remove trailing commas from class/function definitions
        content = re.sub(r"^(\s*class [^:]+):,\s*$", r"\1:", content, flags=re.MULTILINE)
        content = re.sub(r"^(\s*def [^:]+):,\s*$", r"\1:", content, flags=re.MULTILINE)

        # Fix function parameter commas - remove trailing comma after self
        content = re.sub(r"def ([a-zA-Z_][a-zA-Z0-9_]*)\(\s*self,?\s*\n", r"def \1(self,\n", content)

        # Fix return statements with trailing commas
        content = re.sub(r"^(\s*return [^,\n]+),\s*$", r"\1", content, flags=re.MULTILINE)

        if content != original:
            # Test syntax before writing
            try:
                ast.parse(content)
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(content)
                print(f"RESTORED: {file_path}")
                return True
            except SyntaxError as e:
                print(f"SYNTAX ERROR after fix in {file_path}: {e}")
                return False
        else:
            print(f"NO CHANGES: {file_path}")
            return True

    except Exception as e:
        print(f"ERROR processing {file_path}: {e}")
        return False


def main():
    """Emergency restoration of critical files."""
    base_path = Path("C:/git/hive")

    # Critical files that are blocking pytest collection
    critical_files = [
        "apps/ecosystemiser/src/ecosystemiser/core/errors.py",
        "apps/ecosystemiser/src/ecosystemiser/core/events.py",
        "apps/ecosystemiser/src/ecosystemiser/hive_error_handling.py",
        "apps/ecosystemiser/src/ecosystemiser/system_model/components/energy/heat_buffer.py",
        "apps/ecosystemiser/src/EcoSystemiser/discovery/algorithms/base.py",
    ]

    print("EMERGENCY: Restoring linter-corrupted critical files...")
    print("=" * 60)

    success_count = 0
    for file_path in critical_files:
        full_path = base_path / file_path
        if full_path.exists():
            if emergency_fix_file(full_path):
                success_count += 1
        else:
            print(f"NOT FOUND: {full_path}")

    print("=" * 60)
    print(f"Restored: {success_count}/{len(critical_files)} files")

    if success_count == len(critical_files):
        print("SUCCESS: All critical files restored!")
    else:
        print("WARNING: Some files still need manual attention")


if __name__ == "__main__":
    main()
