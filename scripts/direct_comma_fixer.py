#!/usr/bin/env python3
"""
Direct Comma Fixer - Add commas where they're clearly missing.

This approach:
1. Reads the file line by line
2. Looks for lines that should end with comma based on next line pattern
3. Adds comma if missing
"""

from pathlib import Path


def should_have_comma(line: str, next_line: str) -> bool:
    """Check if current line should have comma based on next line."""
    line = line.strip()
    next_line = next_line.strip()

    # Skip if line already has comma, or is empty, or is comment
    if not line or line.endswith(",") or line.startswith("#"):
        return False

    # Skip certain endings that shouldn't have commas
    if line.endswith(("{", "(", "[", ":", "\\", "+", "-", "*", "/", "=", "==")):
        return False

    # Check if next line indicates we're in a structure that needs commas
    comma_indicators = [
        # Dictionary/object patterns
        '"',  # "key":
        "'",  # 'key':
        # Function call patterns
        "datetime.now()",
        "json.dumps(",
        # Variable names (common in tuples/function calls)
        "task_id",
        "event_type",
        "details",
        "timestamp",
    ]

    # If current line looks like a value and next line has comma indicator
    if any(indicator in next_line for indicator in comma_indicators):
        # Additional checks for common patterns
        if (
            ('"' in line and ":" in line)
            or ("'" in line and ":" in line)
            or line.endswith("]")
            or line.endswith(")")
            or ("row[" in line and "]" in line)
        ):
            return True

    return False


def add_missing_commas(content: str) -> str:
    """Add missing commas to content."""
    lines = content.split("\n")
    result_lines = []

    for i, line in enumerate(lines):
        # Check if we should add comma to this line
        if i < len(lines) - 1:  # Not the last line
            next_line = lines[i + 1]

            if should_have_comma(line, next_line):
                # Add comma
                line = line.rstrip() + ","

        result_lines.append(line)

    return "\n".join(result_lines)


def fix_file_direct(filepath: Path) -> bool:
    """Fix file by adding missing commas."""
    try:
        # Read file
        with open(filepath, encoding="utf-8") as f:
            original = f.read()

        # Apply fix
        fixed = add_missing_commas(original)

        if fixed != original:
            # Write back
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(fixed)

            print(f"FIXED: {filepath}")
            return True
        else:
            print(f"NO CHANGE: {filepath}")
            return True

    except Exception as e:
        print(f"ERROR: {filepath} - {e}")
        return False


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        filepath = Path(sys.argv[1])
        fix_file_direct(filepath)
    else:
        print("Usage: python direct_comma_fixer.py <filepath>")
