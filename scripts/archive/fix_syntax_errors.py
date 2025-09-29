#!/usr/bin/env python3
"""Fix common syntax errors in Python files - missing commas in dicts and function params."""

import re
import sys
from pathlib import Path


def fix_dict_commas(content: str) -> str:
    """Fix missing commas in dictionary definitions."""
    # Pattern: "key": value followed by newline and another "key": pattern
    pattern = r'("[\w_]+"\s*:\s*[^,\n}]+)(\n\s*"[\w_]+"\s*:)'
    content = re.sub(pattern, r"\1,\2", content)

    # Pattern: 'key': value followed by newline and another 'key': pattern
    pattern = r"('[\w_]+'\s*:\s*[^,\n}]+)(\n\s*'[\w_]+'\s*:)"
    content = re.sub(pattern, r"\1,\2", content)

    return content


def fix_function_params(content: str) -> str:
    """Fix missing commas in function parameters."""
    lines = content.split("\n")
    fixed_lines = []
    in_function_def = False
    param_lines = []

    for i, line in enumerate(lines):
        # Detect function definition start
        if re.match(r"\s*(def|async def)\s+\w+\s*\(", line):
            in_function_def = True
            param_lines = [line]
        elif in_function_def:
            param_lines.append(line)
            # Check if we've reached the end of the function definition
            if ")" in line and ":" in line:
                # Process the collected lines
                full_def = "\n".join(param_lines)
                # Fix missing commas after 'self'
                full_def = re.sub(r"(\bself\b)(\n\s+\w+)", r"\1,\2", full_def)
                # Fix missing commas in parameters
                full_def = re.sub(r"(:\s*[^\n,)]+)(\n\s+\w+\s*:)", r"\1,\2", full_def)
                # Fix missing commas before **kwargs
                full_def = re.sub(r"([^\n,]+)(\n\s+\*\*kwargs)", r"\1,\2", full_def)

                fixed_lines.extend(full_def.split("\n"))
                in_function_def = False
                param_lines = []
            # Continue collecting lines
        else:
            fixed_lines.append(line)

    # Add any remaining lines
    if param_lines:
        fixed_lines.extend(param_lines)

    return "\n".join(fixed_lines)


def fix_file(file_path: Path) -> bool:
    """Fix syntax errors in a single file."""
    try:
        content = file_path.read_text()
        original = content

        # Apply fixes
        content = fix_dict_commas(content)
        content = fix_function_params(content)

        if content != original:
            file_path.write_text(content)
            print(f"Fixed: {file_path}")
            return True
        return False
    except Exception as e:
        print(f"Error fixing {file_path}: {e}")
        return False


def main():
    """Fix syntax errors in hive-errors package."""
    errors_dir = Path("packages/hive-errors/src/hive_errors")

    if not errors_dir.exists():
        print(f"Directory not found: {errors_dir}")
        sys.exit(1)

    fixed_count = 0
    for py_file in errors_dir.glob("*.py"):
        if fix_file(py_file):
            fixed_count += 1

    print(f"\nFixed {fixed_count} files")

    # Also fix hive-db package
    db_dir = Path("packages/hive-db/src/hive_db")
    if db_dir.exists():
        for py_file in db_dir.glob("*.py"):
            if fix_file(py_file):
                fixed_count += 1

    print(f"Total files fixed: {fixed_count}")


if __name__ == "__main__":
    main()
