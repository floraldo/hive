#!/usr/bin/env python3
"""
Simple Comma Fixer - One powerful regex to rule them all.

This script uses a simple but effective approach:
- Find lines that look like dictionary entries: "key": value
- If the next line also looks like a dictionary entry and the current line doesn't end with comma
- Add the comma
"""

import ast
import re
from pathlib import Path


def fix_commas_simple(content: str) -> str:
    """Fix missing commas with a simple but effective regex."""

    # Main pattern: dictionary entry without comma followed by another dictionary entry
    # Matches: "key": value\n    "nextkey": nextvalue
    # Adds comma after the value
    content = re.sub(r'^(\s*"[^"]+"\s*:\s*[^,\n}]+)(\n\s*"[^"]+"\s*:)', r"\1,\2", content, flags=re.MULTILINE)

    # Also handle single quotes
    content = re.sub(r"^(\s*'[^']+'\s*:\s*[^,\n}]+)(\n\s*'[^']+'\s*:)", r"\1,\2", content, flags=re.MULTILINE)

    return content


def fix_file(filepath: Path) -> bool:
    """Fix a single file."""
    try:
        with open(filepath, encoding="utf-8") as f:
            original = f.read()

        # Apply fix
        fixed = fix_commas_simple(original)

        # Check if it's valid now
        try:
            ast.parse(fixed)

            # Write if changed
            if fixed != original:
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(fixed)
                print(f"FIXED: {filepath}")
                return True
            else:
                print(f"OK: {filepath}")
                return True

        except SyntaxError as e:
            print(f"STILL BROKEN: {filepath} - {e}")
            return False

    except Exception as e:
        print(f"ERROR: {filepath} - {e}")
        return False


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        # Fix specific file
        filepath = Path(sys.argv[1])
        success = fix_file(filepath)
        sys.exit(0 if success else 1)
    else:
        print("Usage: python simple_comma_fixer.py <filepath>")
        sys.exit(1)
