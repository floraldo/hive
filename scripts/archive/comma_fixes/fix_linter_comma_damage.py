#!/usr/bin/env python3
"""
Emergency fix for linter-introduced comma damage.

The linters have systematically corrupted the codebase by adding trailing commas
in wrong locations like function parameters, causing widespread syntax errors.
"""

import ast
import os
import re
from pathlib import Path
from typing import List, Tuple


def fix_comma_errors(file_content: str) -> Tuple[str, bool]:
    """Fix common comma errors introduced by automated tools."""
    original = file_content

    # Remove trailing commas after single statements
    file_content = re.sub(r"^(\s*)([^,\n#]+),\s*$", r"\1\2", file_content, flags=re.MULTILINE)

    return file_content, file_content != original


def check_syntax(filepath: Path) -> Tuple[bool, str]:
    """Check if file has valid Python syntax."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            source = f.read()
        ast.parse(source, filename=str(filepath))
        return True, "OK"
    except SyntaxError as e:
        return False, f"SyntaxError line {e.lineno}: {e.msg}"
    except Exception as e:
        return False, f"Error: {e}"


def fix_file(filepath: Path) -> bool:
    """Fix comma errors in a single file."""
    try:
        # Check original syntax
        valid_before, error_before = check_syntax(filepath)

        with open(filepath, "r", encoding="utf-8") as f:
            original_content = f.read()

        fixed_content, was_changed = fix_comma_errors(original_content)

        if was_changed:
            # Write fixed content
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(fixed_content)

            # Check new syntax
            valid_after, error_after = check_syntax(filepath)

            if valid_after:
                print(f"FIXED: {filepath}")
                return True
            else:
                print(f"BROKEN: {filepath} - {error_after}")
                # Restore original if we broke it
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(original_content)
                return False
        else:
            if not valid_before:
                print(f"UNCHANGED: {filepath} - {error_before}")
            return valid_before

    except Exception as e:
        print(f"ERROR processing {filepath}: {e}")
        return False


def main():
    """Fix linter-introduced comma damage across the codebase."""
    base_path = Path("C:/git/hive")

    # Focus on recently modified Python files
    python_files = [
        "apps/ecosystemiser/src/ecosystemiser/core/errors.py",
        "apps/ecosystemiser/src/ecosystemiser/core/events.py",
        "apps/ecosystemiser/src/ecosystemiser/hive_error_handling.py",
        "apps/ecosystemiser/src/ecosystemiser/system_model/components/energy/heat_buffer.py",
        "apps/ecosystemiser/src/EcoSystemiser/discovery/algorithms/base.py",
    ]

    fixed_count = 0
    total_count = len(python_files)

    print("EMERGENCY: Fixing linter-introduced comma damage...")
    print("=" * 60)

    for file_path in python_files:
        full_path = base_path / file_path
        if full_path.exists():
            if fix_file(full_path):
                fixed_count += 1
        else:
            print(f"NOT FOUND: {full_path}")

    print("=" * 60)
    print(f"Fixed: {fixed_count}/{total_count} files")


if __name__ == "__main__":
    main()
