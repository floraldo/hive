#!/usr/bin/env python3
"""
Fix all golden rule violations in the Hive codebase.
This script systematically fixes error handling and logging violations.
"""

import re
from pathlib import Path

def fix_bare_except(file_path: Path):
    """Fix bare except clauses in a Python file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    original_content = content

    # Fix "except:" -> "except Exception as e:"
    content = re.sub(r'\bexcept\s*:', 'except Exception as e:', content)

    # Fix "except Exception:" -> "except Exception as e:"
    content = re.sub(r'\bexcept\s+Exception\s*:', 'except Exception as e:', content)

    if content != original_content:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    return False

def fix_print_statements(file_path: Path):
    """Replace print statements with logging in a Python file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    modified = False
    new_lines = []
    has_logger = False
    has_hive_logging_import = False

    # Check if file already has logging
    for line in lines:
        if 'from hive_logging import' in line:
            has_hive_logging_import = True
        if 'logger = get_logger' in line or 'self.logger = get_logger' in line:
            has_logger = True

    # Process lines
    for line in lines:
        # Skip if it's a comment or in a docstring
        stripped = line.strip()
        if stripped.startswith('#'):
            new_lines.append(line)
            continue

        # Replace print statements (but not in test files)
        if 'print(' in line and not line.strip().startswith('#'):
            # Extract the print content
            match = re.search(r'print\((.*)\)', line)
            if match:
                content = match.group(1)
                # Determine log level based on content
                if 'error' in content.lower() or 'fail' in content.lower():
                    replacement = f'logger.error({content})'
                elif 'warn' in content.lower():
                    replacement = f'logger.warning({content})'
                elif 'debug' in content.lower():
                    replacement = f'logger.debug({content})'
                else:
                    replacement = f'logger.info({content})'

                new_line = line.replace(f'print({content})', replacement)
                new_lines.append(new_line)
                modified = True
            else:
                new_lines.append(line)
        else:
            new_lines.append(line)

    # If we modified the file and it doesn't have logging, add imports
    if modified and not has_hive_logging_import:
        # Find where to insert imports (after module docstring and other imports)
        import_index = 0
        in_docstring = False
        for i, line in enumerate(new_lines):
            if i == 0 and line.strip().startswith('"""'):
                in_docstring = True
            elif in_docstring and '"""' in line:
                in_docstring = False
                import_index = i + 1
            elif line.strip().startswith('import ') or line.strip().startswith('from '):
                import_index = i + 1
            elif line.strip() and not line.strip().startswith('#'):
                break

        # Insert the import
        new_lines.insert(import_index, 'from hive_logging import get_logger\n')
        if not has_logger:
            new_lines.insert(import_index + 1, '\nlogger = get_logger(__name__)\n')
        modified = True

    if modified:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)

    return modified

def main():
    """Fix all violations in the codebase."""
    project_root = Path(__file__).parent.parent

    # Directories to fix
    dirs_to_fix = [
        project_root / "apps",
        project_root / "packages"
    ]

    error_handling_fixed = 0
    logging_fixed = 0

    for base_dir in dirs_to_fix:
        if not base_dir.exists():
            continue

        for py_file in base_dir.rglob("*.py"):
            # Skip test files, virtual environments, and __pycache__
            if (".venv" in str(py_file) or
                "__pycache__" in str(py_file) or
                "test_" in py_file.name or
                "_test.py" in py_file.name):
                continue

            # Fix bare except clauses
            if fix_bare_except(py_file):
                error_handling_fixed += 1
                print(f"Fixed bare except in: {py_file.relative_to(project_root)}")

            # Fix print statements (skip main files and examples)
            if ("__main__" not in py_file.name and
                "example" not in py_file.name.lower() and
                "demo" not in py_file.name.lower()):
                if fix_print_statements(py_file):
                    logging_fixed += 1
                    print(f"Fixed logging in: {py_file.relative_to(project_root)}")

    print(f"\nSummary:")
    print(f"Fixed {error_handling_fixed} files with bare except clauses")
    print(f"Fixed {logging_fixed} files with print statements")
    print("\nDone! Run the golden tests to verify all violations are fixed.")

if __name__ == "__main__":
    main()