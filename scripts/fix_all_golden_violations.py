#!/usr/bin/env python3
"""Fix all golden rule violations in the codebase."""

import ast
import re
from pathlib import Path
from typing import Set, List

def fix_bare_except_clauses(file_path: Path) -> bool:
    """Fix bare except clauses by adding Exception type."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        original_content = content

        # Fix bare except: clauses
        lines = content.split('\n')
        new_lines = []
        for line in lines:
            if line.strip() == "except:":
                # Preserve indentation
                indent = line[:len(line) - len(line.lstrip())]
                new_lines.append(f"{indent}except Exception as e:")
            else:
                new_lines.append(line)

        content = '\n'.join(new_lines)

        if content != original_content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return True

        return False
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return False

def fix_print_statements(file_path: Path) -> bool:
    """Replace print statements with logging calls."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        original_content = content

        # Check if the file is using console.print from rich
        if "from rich.console import Console" in content or "console.print(" in content:
            # Replace console.print with logger calls
            if "from hive_logging import get_logger" not in content:
                # Add import at the top
                import_line = "from hive_logging import get_logger\n\nlogger = get_logger(__name__)\n"
                if content.startswith('"""'):
                    # Find end of docstring
                    end_docstring = content.find('"""', 3)
                    if end_docstring != -1:
                        content = content[:end_docstring + 3] + "\n\n" + import_line + content[end_docstring + 3:]
                else:
                    content = import_line + content

            # Replace console.print calls with logger.info
            content = re.sub(r'console\.print\((.*?)\)', r'logger.info(\1)', content)

        # Replace regular print statements
        if "print(" in content and "test" not in str(file_path).lower():
            # Add logging import if not present
            if "from hive_logging import get_logger" not in content and "import hive_logging" not in content:
                # Add import at the top
                import_line = "from hive_logging import get_logger\n\nlogger = get_logger(__name__)\n"
                if content.startswith('"""'):
                    # Find end of docstring
                    end_docstring = content.find('"""', 3)
                    if end_docstring != -1:
                        content = content[:end_docstring + 3] + "\n\n" + import_line + content[end_docstring + 3:]
                else:
                    content = import_line + content

            # Replace print() statements with logger.info()
            content = re.sub(r'\bprint\((.*?)\)', r'logger.info(\1)', content)

        if content != original_content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return True

        return False
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return False

def fix_logging_imports(file_path: Path) -> bool:
    """Ensure files using logging import from hive_logging."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        original_content = content

        # Check if file uses logging but not hive_logging
        if ("logger" in content.lower() or "logging" in content.lower()):
            if "from hive_logging import" not in content and "import hive_logging" not in content:
                # Skip infrastructure packages
                if "hive-logging" not in str(file_path) and "hive-testing-utils" not in str(file_path) and "hive-config" not in str(file_path):
                    # Replace standard logging with hive_logging
                    if "import logging" in content:
                        content = content.replace("import logging", "from hive_logging import get_logger")
                        content = re.sub(r'logging\.getLogger\((.*?)\)', r'get_logger(\1)', content)
                        content = re.sub(r'logger = logging\.getLogger\((.*?)\)', r'logger = get_logger(\1)', content)
                    elif "from logging import" in content:
                        content = re.sub(r'from logging import .*', 'from hive_logging import get_logger', content)
                        content = re.sub(r'getLogger\((.*?)\)', r'get_logger(\1)', content)

        if content != original_content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return True

        return False
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return False

def main():
    """Main function to fix all violations."""
    project_root = Path(__file__).parent.parent

    bare_except_fixed = 0
    print_fixed = 0
    logging_fixed = 0

    for base_dir in [project_root / "apps", project_root / "packages"]:
        if not base_dir.exists():
            continue

        for py_file in base_dir.rglob("*.py"):
            # Skip test files and virtual environments
            if (".venv" in str(py_file) or "__pycache__" in str(py_file) or
                "test" in str(py_file) or "demo" in str(py_file) or
                "example" in str(py_file)):
                continue

            # Fix bare except clauses
            if fix_bare_except_clauses(py_file):
                bare_except_fixed += 1
                print(f"Fixed bare except in: {py_file.relative_to(project_root)}")

            # Fix print statements
            if fix_print_statements(py_file):
                print_fixed += 1
                print(f"Fixed print statements in: {py_file.relative_to(project_root)}")

            # Fix logging imports
            if fix_logging_imports(py_file):
                logging_fixed += 1
                print(f"Fixed logging imports in: {py_file.relative_to(project_root)}")

    print("\nSummary:")
    print(f"Fixed {bare_except_fixed} files with bare except clauses")
    print(f"Fixed {print_fixed} files with print statements")
    print(f"Fixed {logging_fixed} files with logging imports")
    print("\nDone! Run the golden tests to verify all violations are fixed.")

if __name__ == "__main__":
    main()