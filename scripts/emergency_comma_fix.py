#!/usr/bin/env python3
"""
Emergency Comma Fix - Ultra-simple comma addition for dictionary patterns.

This tool does ONE thing: adds commas to dictionary-like structures.
It uses a simple heuristic:
- If a line matches pattern: whitespace + "key": value (no trailing comma)
- AND next line matches pattern: whitespace + "key":
- THEN add comma to first line

This is aggressive but should fix the majority of missing comma issues.
"""

import ast
import re
from pathlib import Path


def add_dict_commas(content: str) -> str:
    """Add commas to dictionary patterns."""

    lines = content.split("\n")
    fixed_lines = []

    for i, line in enumerate(lines):
        # Look for dictionary patterns
        if (
            i < len(lines) - 1
            and
            # Current line looks like: "key": value (without comma)
            re.match(r'^\s*"[^"]+"\s*:\s*[^,\n{}]+\s*$', line)
            and
            # Next line looks like: "key":
            re.match(r'^\s*"[^"]+"\s*:', lines[i + 1])
        ):
            # Add comma
            line = line.rstrip() + ","

        fixed_lines.append(line)

    return "\n".join(fixed_lines)


def bulk_fix_files():
    """Apply comma fix to all problematic files."""

    # Get all Python files with syntax errors
    problem_files = []
    patterns = ["apps/**/*.py", "packages/**/*.py"]

    print("Finding files with comma syntax errors...")

    for pattern in patterns:
        files = list(Path(".").glob(pattern))
        for filepath in files:
            if any(skip in str(filepath) for skip in [".venv", "__pycache__", ".git"]):
                continue

            try:
                with open(filepath, encoding="utf-8") as f:
                    content = f.read()
                ast.parse(content)
            except SyntaxError as e:
                if "comma" in str(e).lower() or "perhaps you forgot" in str(e).lower():
                    problem_files.append(filepath)
            except:
                pass

    print(f"Found {len(problem_files)} files with comma syntax errors")

    fixed_count = 0

    for filepath in problem_files:
        try:
            with open(filepath, encoding="utf-8") as f:
                original = f.read()

            fixed = add_dict_commas(original)

            if fixed != original:
                # Validate fix
                try:
                    ast.parse(fixed)
                    # Write fixed version
                    with open(filepath, "w", encoding="utf-8") as f:
                        f.write(fixed)
                    print(f"FIXED: {filepath}")
                    fixed_count += 1
                except SyntaxError:
                    print(f"PARTIAL: {filepath} (some fixes applied)")
                    # Write partial fix anyway - it might help
                    with open(filepath, "w", encoding="utf-8") as f:
                        f.write(fixed)
            else:
                print(f"NO CHANGE: {filepath}")

        except Exception as e:
            print(f"ERROR: {filepath} - {e}")

    print(f"\nCompleted: {fixed_count} files successfully fixed")


if __name__ == "__main__":
    bulk_fix_files()
