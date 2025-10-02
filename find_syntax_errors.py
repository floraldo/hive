#!/usr/bin/env python
"""Find all Python files with syntax errors."""

import subprocess
from pathlib import Path

def check_syntax(file_path: Path) -> tuple[bool, str]:
    """Check if a Python file has syntax errors."""
    try:
        subprocess.run(
            ['python', '-m', 'py_compile', str(file_path)],
            capture_output=True,
            text=True,
            check=True
        )
        return True, ""
    except subprocess.CalledProcessError as e:
        return False, e.stderr

def main():
    """Check all Python files for syntax errors."""
    project_root = Path(__file__).parent

    # Find all Python files
    python_files = []
    for pattern in ['apps/**/*.py', 'packages/**/*.py', 'scripts/**/*.py', 'tests/**/*.py']:
        python_files.extend(project_root.glob(pattern))

    errors_found = []

    for file_path in python_files:
        if file_path.name in ['find_syntax_errors.py', 'fix_invalid_commas.py', 'fix_trailing_commas.py']:
            continue

        success, error = check_syntax(file_path)
        if not success:
            errors_found.append((file_path, error))

    if errors_found:
        print(f"Found {len(errors_found)} files with syntax errors:\n")
        for file_path, error in errors_found[:20]:  # Show first 20
            print(f"{file_path.relative_to(project_root)}")
            # Extract just the error line
            for line in error.split('\n'):
                if 'SyntaxError' in line or 'line' in line.lower():
                    print(f"  {line.strip()}")
            print()
    else:
        print("No syntax errors found!")

    return len(errors_found)

if __name__ == '__main__':
    exit(main())
