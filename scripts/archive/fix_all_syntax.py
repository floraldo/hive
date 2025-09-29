#!/usr/bin/env python3
"""Comprehensive syntax error fixer for all Hive packages."""

import os
import subprocess
import sys
from pathlib import Path


def check_syntax(file_path):
    """Check if a file has syntax errors."""
    try:
        result = subprocess.run([sys.executable, "-m", "py_compile", str(file_path)], capture_output=True, text=True)
        if result.returncode != 0:
            return result.stderr
        return None
    except Exception as e:
        return str(e)


def find_and_fix_syntax_errors():
    """Find all Python files with syntax errors and report them."""
    packages_dir = Path("packages")
    apps_dir = Path("apps")

    error_files = []

    # Check all Python files
    for directory in [packages_dir, apps_dir]:
        if directory.exists():
            for py_file in directory.rglob("*.py"):
                error = check_syntax(py_file)
                if error:
                    error_files.append((py_file, error))
                    print(f"ERROR in {py_file}:")
                    # Extract just the error line
                    for line in error.split("\n"):
                        if "SyntaxError" in line or "line" in line:
                            print(f"  {line}")

    return error_files


def main():
    """Main function."""
    print("Searching for syntax errors in all Python files...")
    print("=" * 80)

    error_files = find_and_fix_syntax_errors()

    if error_files:
        print("\n" + "=" * 80)
        print(f"Found {len(error_files)} files with syntax errors:")
        for file_path, _ in error_files:
            print(f"  - {file_path}")
    else:
        print("\nNo syntax errors found!")

    return len(error_files)


if __name__ == "__main__":
    sys.exit(main())
