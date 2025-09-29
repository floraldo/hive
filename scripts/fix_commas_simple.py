#!/usr/bin/env python3
"""
Simple Missing Comma Fixer

A straightforward approach to fix the most common comma pattern:
Lines that should end with commas but don't.
"""

import ast
from pathlib import Path


def fix_file_commas(file_path: Path) -> bool:
    """Fix missing commas in a file using simple heuristics."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Check if already valid
        try:
            ast.parse(content)
            return True
        except SyntaxError as e:
            if "forgot a comma" not in str(e):
                return False

        lines = content.split("\n")
        fixed_lines = []

        for i, line in enumerate(lines):
            # Check if we need to add a comma
            if should_add_comma(line, lines, i):
                fixed_lines.append(line.rstrip() + ",")
            else:
                fixed_lines.append(line)

        fixed_content = "\n".join(fixed_lines)

        # Test if fix worked
        try:
            ast.parse(fixed_content)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(fixed_content)
            return True
        except SyntaxError:
            return False

    except Exception:
        return False


def should_add_comma(line: str, all_lines: list, line_idx: int) -> bool:
    """Determine if a line should have a comma added."""
    stripped = line.strip()

    # Skip empty lines, comments, lines ending with specific chars
    if not stripped or stripped.startswith("#") or stripped.endswith((",", ")", "]", "}", ":", "\\")):
        return False

    # Skip certain line types
    skip_patterns = [
        "def ",
        "class ",
        "if ",
        "elif ",
        "else:",
        "for ",
        "while ",
        "with ",
        "try:",
        "except",
        "finally:",
        "import ",
        "from ",
    ]
    if any(stripped.startswith(pattern) for pattern in skip_patterns):
        return False

    # Look ahead to see what comes next
    next_line_idx = line_idx + 1
    while next_line_idx < len(all_lines) and not all_lines[next_line_idx].strip():
        next_line_idx += 1

    if next_line_idx >= len(all_lines):
        return False

    next_line = all_lines[next_line_idx].strip()

    # Don't add comma if next line starts with closing bracket
    if next_line.startswith(("}", ")", "]")):
        return False

    # Add comma if line looks like it should be part of a list/dict/function call
    # and the next line continues the pattern
    line_patterns = [
        # String literals
        (stripped.startswith('"') and stripped.endswith('"')),
        (stripped.startswith("'") and stripped.endswith("'")),
        # Key-value pairs
        "=" in stripped,
        # Function parameters/arguments
        ":" in stripped and not stripped.endswith(":"),
        # Simple identifiers/numbers
        stripped.replace("_", "").replace(".", "").isalnum(),
        # Expressions ending with parentheses or brackets
        stripped.endswith(")") or stripped.endswith("]"),
    ]

    next_patterns = [
        # Next line looks like continuation
        next_line.startswith('"') or next_line.startswith("'"),
        "=" in next_line,
        ":" in next_line,
        next_line.replace("_", "").replace(".", "").isalnum(),
        next_line.startswith("(") or next_line.startswith("[") or next_line.startswith("{"),
    ]

    return any(line_patterns) and any(next_patterns)


def main():
    """Fix comma errors in critical files."""
    project_root = Path(__file__).parent.parent

    # Critical files that are blocking imports
    critical_files = [
        "packages/hive-config/src/hive_config/unified_config.py",
        "packages/hive-ai/src/hive_ai/models/client.py",
        "packages/hive-ai/src/hive_ai/core/exceptions.py",
        "packages/hive-ai/src/hive_ai/core/config.py",
        "packages/hive-db/src/hive_db/postgres_connector.py",
        "apps/ecosystemiser/src/ecosystemiser/core/errors.py",
    ]

    print("Simple Comma Fixer - Processing critical files...")

    for file_str in critical_files:
        file_path = project_root / file_str
        if file_path.exists():
            if fix_file_commas(file_path):
                print(f"FIXED: {file_str}")
            else:
                print(f"FAILED: {file_str}")


if __name__ == "__main__":
    main()
