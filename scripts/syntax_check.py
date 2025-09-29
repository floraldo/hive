#!/usr/bin/env python3
"""
Quick syntax validation script for Hive agents.
Prevents comma-related syntax errors that caused the Code Red crisis.
"""

import ast
import sys
from pathlib import Path


def check_file_syntax(filepath: Path) -> tuple[bool, str]:
    """Check if a Python file has valid syntax."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            source = f.read()

        # Try to compile the file
        ast.parse(source, filename=str(filepath))
        return True, "OK"

    except SyntaxError as e:
        return False, f"SyntaxError line {e.lineno}: {e.msg}"
    except Exception as e:
        return False, f"Error: {e}"


def main():
    """Check syntax of specified files or all Python files."""
    if len(sys.argv) < 2:
        print("Usage: python scripts/syntax_check.py <file1.py> [file2.py] ...")
        sys.exit(1)

    all_valid = True

    for filepath_str in sys.argv[1:]:
        filepath = Path(filepath_str)

        if not filepath.exists():
            print(f"FAIL {filepath}: File not found")
            all_valid = False
            continue

        if not filepath.suffix == ".py":
            print(f"SKIP {filepath}: Not a Python file, skipping")
            continue

        is_valid, message = check_file_syntax(filepath)

        if is_valid:
            print(f"OK {filepath}: {message}")
        else:
            print(f"FAIL {filepath}: {message}")
            all_valid = False

    if not all_valid:
        print("\nSYNTAX ERRORS DETECTED - Fix before committing!")
        sys.exit(1)
    else:
        print("\nAll files have valid syntax")


if __name__ == "__main__":
    main()
