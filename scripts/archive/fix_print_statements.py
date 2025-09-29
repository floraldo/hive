#!/usr/bin/env python3
"""Fix print statements to use proper logging - Golden Rule 9."""

import re
from pathlib import Path
from typing import Set, Tuple


def fix_print_to_logging(content: str, file_path: Path) -> Tuple[str, int]:
    """Replace print statements with proper logging."""
    lines = content.split("\n")
    fixed_lines = []
    changes = 0
    has_logger = False

    # Check if logger is already imported
    for line in lines:
        if "from hive_logging import get_logger" in line:
            has_logger = True
            break
        if "logger = get_logger" in line:
            has_logger = True
            break

    # Add logger import if needed
    if not has_logger and "print(" in content:
        # Find where to insert the import (after other imports)
        import_index = 0
        for i, line in enumerate(lines):
            if line.strip() and not line.startswith("#") and not line.startswith('"""'):
                if "import" in line or "from" in line:
                    import_index = i + 1
                else:
                    break

        if import_index == 0:
            # No imports found, add after module docstring if exists
            in_docstring = False
            for i, line in enumerate(lines):
                if line.strip().startswith('"""'):
                    if in_docstring:
                        import_index = i + 1
                        break
                    in_docstring = True
                elif in_docstring and '"""' in line:
                    import_index = i + 1
                    break

        # Insert the import and logger initialization
        if import_index > 0:
            lines.insert(import_index, "")
            lines.insert(import_index + 1, "from hive_logging import get_logger")
            lines.insert(import_index + 2, "")
            lines.insert(import_index + 3, "logger = get_logger(__name__)")
            has_logger = True
            changes += 1

    # Process each line
    for i, line in enumerate(lines):
        original_line = line

        # Skip if it's a comment or docstring
        if line.strip().startswith("#"):
            fixed_lines.append(line)
            continue

        # Simple print() statements
        if "print(" in line and has_logger:
            # Handle various print patterns
            patterns = [
                (r'print\(f"([^"]+)"\)', r'logger.info("\1")'),
                (r"print\(f\'([^\']+)\'\)", r'logger.info("\1")'),
                (r'print\("([^"]+)"\)', r'logger.info("\1")'),
                (r"print\(\'([^\']+)\'\)", r'logger.info("\1")'),
                (r"print\(([^)]+)\)", r"logger.info(\1)"),
            ]

            for pattern, replacement in patterns:
                if re.search(pattern, line):
                    line = re.sub(pattern, replacement, line)
                    changes += 1
                    break

        fixed_lines.append(line)

    return "\n".join(fixed_lines), changes


def should_skip_file(file_path: Path) -> bool:
    """Check if file should be skipped."""
    skip_patterns = ["test_", "_test.py", "tests/", "debug", "demo", "example", "scripts/", "archive/"]

    path_str = str(file_path).lower()
    for pattern in skip_patterns:
        if pattern in path_str:
            return True
    return False


def main():
    """Fix print statements in all Python files."""
    apps_dir = Path("apps")

    if not apps_dir.exists():
        print(f"Directory not found: {apps_dir}")
        return

    files_fixed = 0
    total_changes = 0

    # Find all Python files with print statements
    for py_file in apps_dir.rglob("*.py"):
        # Skip test files and scripts
        if should_skip_file(py_file):
            continue

        try:
            content = py_file.read_text()

            # Skip if no print statements
            if "print(" not in content:
                continue

            # Fix print statements
            fixed_content, changes = fix_print_to_logging(content, py_file)

            if changes > 0:
                py_file.write_text(fixed_content)
                print(f"Fixed {changes} print statements in: {py_file}")
                files_fixed += 1
                total_changes += changes

        except Exception as e:
            print(f"Error processing {py_file}: {e}")

    print(f"\nTotal: Fixed {total_changes} print statements in {files_fixed} files")


if __name__ == "__main__":
    main()
