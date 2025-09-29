#!/usr/bin/env python
"""
Fix print statements across the codebase by converting them to proper hive_logging.

This script will:
1. Find all print statements in production code
2. Convert them to proper hive_logging calls
3. Add necessary imports if missing
"""

import re
from pathlib import Path


def is_test_file(filepath: Path) -> bool:
    """Check if file is a test file."""
    return (
        "test" in filepath.parts
        or filepath.name.startswith("test_")
        or filepath.name.endswith("_test.py")
        or "/tests/" in str(filepath)
    )


def fix_print_statements(filepath: Path) -> bool:
    """Fix print statements in a single file."""
    if is_test_file(filepath):
        return False

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
            original = content
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        return False

    # Skip if no print statements
    if "print(" not in content:
        return False

    # Check if hive_logging is already imported
    has_logger_import = "from hive_logging import get_logger" in content
    has_logger_init = "logger = get_logger(__name__)" in content

    lines = content.split("\n")
    modified = False
    new_lines = []

    # Process each line
    for line in lines:
        # Skip if line is in a comment or string
        stripped = line.strip()
        if stripped.startswith("#") or stripped.startswith('"""') or stripped.startswith("'''"):
            new_lines.append(line)
            continue

        # Look for print statements
        if re.match(r"\s*print\s*\(", line):
            # Extract the print content
            match = re.match(r"(\s*)print\s*\((.*)\)", line)
            if match:
                indent = match.group(1)
                content_part = match.group(2)

                # Handle f-strings and format strings
                if content_part.startswith('f"') or content_part.startswith("f'"):
                    # f-string - use directly
                    new_line = f"{indent}logger.info({content_part})"
                elif '".format(' in content_part or "'.format(" in content_part:
                    # .format() string - use directly
                    new_line = f"{indent}logger.info({content_part})"
                elif "%" in content_part and ("," in content_part or " % " in content_part):
                    # % formatting - convert to f-string if simple
                    new_line = f"{indent}logger.info({content_part})"
                else:
                    # Simple string or variable
                    new_line = f"{indent}logger.info({content_part})"

                new_lines.append(new_line)
                modified = True
            else:
                new_lines.append(line)
        else:
            new_lines.append(line)

    if not modified:
        return False

    # Add imports if needed
    if modified and not has_logger_import:
        # Find the right place to add imports (after module docstring and other imports)
        import_index = 0
        in_docstring = False
        for i, line in enumerate(new_lines):
            if '"""' in line or "'''" in line:
                in_docstring = not in_docstring
                continue
            if not in_docstring and line.strip() and not line.strip().startswith("#"):
                if line.startswith("import ") or line.startswith("from "):
                    import_index = i + 1
                else:
                    break

        new_lines.insert(import_index, "from hive_logging import get_logger")
        if not has_logger_init:
            new_lines.insert(import_index + 1, "")
            new_lines.insert(import_index + 2, "logger = get_logger(__name__)")
            new_lines.insert(import_index + 3, "")

    # Write back
    try:
        new_content = "\n".join(new_lines)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(new_content)
        return True
    except Exception as e:
        print(f"Error writing {filepath}: {e}")
        return False


def main():
    """Main function to fix print statements across the codebase."""
    base_path = Path("/c/git/hive")

    # Directories to process
    dirs_to_process = [base_path / "apps", base_path / "packages"]

    fixed_count = 0
    error_count = 0

    for dir_path in dirs_to_process:
        if not dir_path.exists():
            continue

        for py_file in dir_path.rglob("*.py"):
            # Skip test files
            if is_test_file(py_file):
                continue

            if fix_print_statements(py_file):
                fixed_count += 1
                print(f"Fixed: {py_file.relative_to(base_path)}")

    print(f"\nCompleted: {fixed_count} files fixed")
    if error_count:
        print(f"Errors: {error_count} files had issues")


if __name__ == "__main__":
    main()
