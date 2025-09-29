#!/usr/bin/env python3
"""
Script to fix all missing commas before **kwargs in events.py.

This script looks for the pattern:
    }
    **kwargs
and fixes it to:
    },
    **kwargs
"""

import re


def fix_kwargs_commas():
    """Fix all missing commas before **kwargs."""

    file_path = r"C:\git\hive\apps\ecosystemiser\src\ecosystemiser\core\events.py"

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        original_content = content

        # Fix pattern: } followed by **kwargs on next line (with optional whitespace)
        # Use re.MULTILINE to handle line boundaries correctly
        content = re.sub(r"(\s*})\s*\n(\s*)(\*\*kwargs)", r"\1,\n\2\3", content, flags=re.MULTILINE)

        if content != original_content:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"Fixed missing comma issues in {file_path}")
            return True
        else:
            print(f"No changes needed in {file_path}")
            return False

    except Exception as e:
        print(f"Error fixing {file_path}: {e}")
        return False


if __name__ == "__main__":
    if fix_kwargs_commas():
        print("PASS: kwargs comma fixing completed")
    else:
        print("FAIL: kwargs comma fixing failed")
