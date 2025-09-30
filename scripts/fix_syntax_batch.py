#!/usr/bin/env python3
"""
Batch syntax error fixer for Project Griffin
Fixes common syntax errors: missing commas in function signatures
"""

import ast
from pathlib import Path


def detect_missing_comma_in_signature(file_path: Path) -> list[tuple[int, str]]:
    """Detect missing commas in function signatures using AST"""
    fixes = []

    try:
        with open(file_path, encoding="utf-8") as f:
            content = f.read()
            lines = content.splitlines()
    except Exception:
        return fixes

    try:
        ast.parse(content)
        return fixes  # No syntax error
    except SyntaxError as e:
        if "Perhaps you forgot a comma" not in e.msg:
            return fixes  # Not a comma issue

        # Try to find and fix the comma issue
        line_num = e.lineno - 1
        if line_num < 0 or line_num >= len(lines):
            return fixes

        line = lines[line_num]

        # Common pattern: type hint without trailing comma
        # Example: "param: Type" should be "param: Type,"
        # Look for pattern: ends with type hint, next line has another param
        if line_num + 1 < len(lines):
            current = line.rstrip()
            next_line = lines[line_num + 1].strip()

            # Check if current line looks like a parameter without comma
            # and next line looks like another parameter or closing paren
            if (
                current
                and not current.endswith(",")
                and not current.endswith("(")
                and (next_line.startswith(")") or ":" in next_line or next_line.endswith(","))
            ):
                # Add comma to current line
                fixed_line = current + ","
                fixes.append((line_num, fixed_line))

    return fixes


def apply_fixes(file_path: Path, fixes: list[tuple[int, str]]) -> bool:
    """Apply fixes to file"""
    if not fixes:
        return False

    try:
        with open(file_path, encoding="utf-8") as f:
            lines = f.readlines()

        for line_num, fixed_line in fixes:
            # Preserve indentation
            original = lines[line_num]
            indent = len(original) - len(original.lstrip())
            lines[line_num] = " " * indent + fixed_line + "\n"

        # Write back
        with open(file_path, "w", encoding="utf-8") as f:
            f.writelines(lines)

        # Verify fix worked
        with open(file_path, encoding="utf-8") as f:
            ast.parse(f.read())

        return True
    except Exception:
        return False


def fix_file(file_path: Path) -> bool:
    """Try to fix syntax errors in file"""
    fixes = detect_missing_comma_in_signature(file_path)
    if fixes:
        return apply_fixes(file_path, fixes)
    return False


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        file_path = Path(sys.argv[1])
        if fix_file(file_path):
            print(f"✅ Fixed: {file_path}")
        else:
            print(f"❌ Could not auto-fix: {file_path}")
    else:
        print("Usage: python fix_syntax_batch.py <file_path>")
