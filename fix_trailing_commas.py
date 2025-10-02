#!/usr/bin/env python3
"""Fix trailing comma syntax errors in Python files."""

import re
import sys
from pathlib import Path


def fix_trailing_commas(file_path: Path) -> bool:
    """Fix invalid trailing commas in Python file."""
    try:
        with open(file_path, encoding="utf-8") as f:
            content = f.read()

        original = content

        # Fix trailing commas in statements (not in collections)
        patterns = [
            # Fix: statement,\n
            (
                r"(\w+)\s*,\s*\n(\s*)(if|while|for|try|except|finally|with|class|def|return|pass|break|continue|raise|import|from)",
                r"\1\n\2\3",
            ),
            # Fix: expression,\n with next line not being a continuation
            (r"([\w\)]+)\s*,\s*\n(\s+)([a-z_])", r"\1\n\2\3"),
            # Fix: pass, except, etc with trailing comma
            (r"(pass|break|continue|raise)\s*,\s*\n", r"\1\n"),
            # Fix: await expr,
            (r"(await\s+[\w\.\(\)]+)\s*,\s*\n", r"\1\n"),
        ]

        for pattern, repl in patterns:
            content = re.sub(pattern, repl, content)

        if content != original:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"Fixed: {file_path}")
            return True
        return False

    except Exception as e:
        print(f"Error fixing {file_path}: {e}", file=sys.stderr)
        return False


def main():
    """Fix trailing commas in specified files or directories."""
    if len(sys.argv) < 2:
        print("Usage: python fix_trailing_commas.py <path>")
        sys.exit(1)

    path = Path(sys.argv[1])
    fixed_count = 0

    if path.is_file():
        if fix_trailing_commas(path):
            fixed_count += 1
    elif path.is_dir():
        for py_file in path.rglob("*.py"):
            if fix_trailing_commas(py_file):
                fixed_count += 1

    print(f"\nFixed {fixed_count} files")


if __name__ == "__main__":
    main()
