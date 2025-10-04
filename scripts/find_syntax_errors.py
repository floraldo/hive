#!/usr/bin/env python3
"""Find all Python files with syntax errors."""

import ast
import sys
from pathlib import Path


def check_syntax(filepath: Path) -> tuple[bool, str | None]:
    """Check if file has valid Python syntax."""
    try:
        with open(filepath, encoding="utf-8", errors="ignore") as f:
            content = f.read()
        ast.parse(content, filename=str(filepath))
        return True, None
    except SyntaxError as e:
        return False, f"Line {e.lineno}: {e.msg}"
    except Exception as e:
        return False, f"Error: {e}"


def main():
    """Find all files with syntax errors."""
    broken_files = []

    # Check apps and packages
    for pattern in ["apps/**/*.py", "packages/**/*.py"]:
        for filepath in Path(".").glob(pattern):
            if "archive" in str(filepath) or "__pycache__" in str(filepath):
                continue

            is_valid, error = check_syntax(filepath)
            if not is_valid:
                broken_files.append((str(filepath), error))

    # Print results
    if broken_files:
        print(f"\n🔴 Found {len(broken_files)} files with syntax errors:\n")
        for filepath, error in broken_files:
            print(f"❌ {filepath}")
            print(f"   {error}\n")

        # Print git command to revert
        print("\n📋 Git command to revert these files:")
        print("git checkout HEAD~1 -- \\")
        for filepath, _ in broken_files:
            print(f'  "{filepath}" \\')
        print()

        return 1
    print("\n✅ No syntax errors found!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
