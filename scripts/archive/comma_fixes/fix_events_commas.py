#!/usr/bin/env python3
"""
Targeted script to fix all remaining comma syntax errors in events.py.

This script addresses the specific patterns found by ruff linting.
"""

import re


def fix_events_commas():
    """Fix all comma syntax errors in events.py."""

    file_path = r"C:\git\hive\apps\ecosystemiser\src\ecosystemiser\core\events.py"

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        original_content = content

        # Fix missing commas in function calls - pattern: parameter\n            parameter
        # Matches lines that end with parameter=value followed by line starting with parameter=
        content = re.sub(r"([a-zA-Z_][a-zA-Z0-9_]*=[^\n,]+)\n(\s+)([a-zA-Z_][a-zA-Z0-9_]*=)", r"\1,\n\2\3", content)

        # Fix missing commas in function definitions - pattern: cls\n        parameter:
        content = re.sub(r"(\bcls)\n(\s+)([a-zA-Z_][a-zA-Z0-9_]*\s*:)", r"\1,\n\2\3", content)

        # Fix missing commas before payload= specifically
        content = re.sub(r"([a-zA-Z_][a-zA-Z0-9_]*=[^\n,]+)\n(\s+)(payload=)", r"\1,\n\2\3", content)

        # Fix missing commas before source= specifically
        content = re.sub(r"([a-zA-Z_][a-zA-Z0-9_]*=[^\n,]+)\n(\s+)(source=)", r"\1,\n\2\3", content)

        if content != original_content:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"Fixed comma errors in {file_path}")
            return True
        else:
            print(f"No changes needed in {file_path}")
            return False

    except Exception as e:
        print(f"Error fixing {file_path}: {e}")
        return False


if __name__ == "__main__":
    if fix_events_commas():
        print("✓ Events comma fixing completed")
    else:
        print("✗ Events comma fixing failed")
