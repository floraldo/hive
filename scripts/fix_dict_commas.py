#!/usr/bin/env python3
"""Fix missing commas in dictionary definitions more comprehensively."""

import re
from pathlib import Path


def fix_dict_commas_comprehensive(content: str) -> str:
    """Fix missing commas in dictionary definitions comprehensively."""
    lines = content.split('\n')
    fixed_lines = []

    for i, line in enumerate(lines):
        # If this line ends with a value (not a comma, {, or [) and next line starts with a quote
        if i < len(lines) - 1:
            # Check if current line ends without comma and next starts with a string key
            current_stripped = line.rstrip()
            next_line = lines[i + 1]

            # Pattern: line ends without comma and next line is a dict key
            if (current_stripped and
                not current_stripped.endswith((',', '{', '[', '(', ':')) and
                '"' not in current_stripped[-3:] and  # Not ending with a quote
                re.match(r'\s*["\'][\w_]+["\']\s*:', next_line)):
                # Add comma to end of current line
                fixed_lines.append(line.rstrip() + ',')
            else:
                fixed_lines.append(line)
        else:
            fixed_lines.append(line)

    return '\n'.join(fixed_lines)


def fix_file(file_path: Path) -> bool:
    """Fix syntax errors in a single file."""
    try:
        content = file_path.read_text()
        original = content

        # Apply fixes
        content = fix_dict_commas_comprehensive(content)

        if content != original:
            file_path.write_text(content)
            print(f"Fixed: {file_path}")
            return True
        return False
    except Exception as e:
        print(f"Error fixing {file_path}: {e}")
        return False


def main():
    """Fix the monitoring_error_reporter.py file."""
    file_path = Path("packages/hive-errors/src/hive_errors/monitoring_error_reporter.py")

    if not file_path.exists():
        print(f"File not found: {file_path}")
        return

    if fix_file(file_path):
        print("Fixed monitoring_error_reporter.py")
    else:
        print("No changes needed")


if __name__ == "__main__":
    main()