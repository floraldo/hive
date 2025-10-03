#!/usr/bin/env python3
"""
Surgical Comma Fix - Simple, reliable, transparent

For each file with error:
1. Get exact error line from py_compile
2. Add comma to previous line
3. Validate immediately
4. Revert and stop if validation fails
"""

import re
import subprocess
import sys
from pathlib import Path


def get_error_line(file_path: Path) -> int:
    """Get line number of first syntax error, or 0 if no error"""
    result = subprocess.run(
        ["python", "-m", "py_compile", str(file_path)],
        capture_output=True,
        text=True
    )

    if result.returncode == 0:
        return 0

    match = re.search(r'line (\d+)', result.stderr)
    return int(match.group(1)) if match else 0


def fix_file(file_path: Path) -> bool:
    """
    Fix ALL comma errors in a file.

    Returns:
        True if all errors fixed successfully
    """
    max_iterations = 20  # Safety limit
    iteration = 0

    while iteration < max_iterations:
        error_line = get_error_line(file_path)

        if error_line == 0:
            return True  # All errors fixed!

        iteration += 1

        # Read file
        lines = file_path.read_text(encoding="utf-8").splitlines(keepends=True)

        # The error line itself (0-indexed)
        error_idx = error_line - 1

        if error_idx < 0 or error_idx >= len(lines):
            print(f"  [ERROR] Invalid line index {error_idx}")
            subprocess.run(["git", "restore", str(file_path)], check=True)
            return False

        error_line_text = lines[error_idx].strip()

        # Pattern 1: Decorator with trailing comma (@staticmethod,)
        if error_line_text.startswith('@') and error_line_text.endswith(','):
            lines[error_idx] = lines[error_idx].rstrip().rstrip(',') + '\n'
            file_path.write_text(''.join(lines), encoding="utf-8")
        # Pattern 2: Opening brace/bracket/paren with comma ({, or [, or (,)
        elif '{,' in lines[error_idx] or '[,' in lines[error_idx] or '(,' in lines[error_idx]:
            lines[error_idx] = lines[error_idx].replace('{,', '{').replace('[,', '[').replace('(,', '(')
            file_path.write_text(''.join(lines), encoding="utf-8")
        else:
            # Add comma to line BEFORE error
            fix_idx = error_line - 2

            if fix_idx < 0 or fix_idx >= len(lines):
                print(f"  [ERROR] Invalid fix line index {fix_idx}")
                subprocess.run(["git", "restore", str(file_path)], check=True)
                return False

            line = lines[fix_idx]
            if not line.rstrip().endswith(','):
                lines[fix_idx] = line.rstrip() + ',' + '\n'
                file_path.write_text(''.join(lines), encoding="utf-8")

    # If we hit max iterations, something is wrong
    print("  [ERROR] Max iterations reached")
    subprocess.run(["git", "restore", str(file_path)], check=True)
    return False


def main():
    # Get all Python files
    all_python_files = []
    for dir_path in ["packages", "apps"]:
        all_python_files.extend(Path(dir_path).rglob("*.py"))

    # Check each file for syntax errors
    files_with_errors = []
    for file_path in all_python_files:
        if get_error_line(file_path) > 0:
            files_with_errors.append(file_path)

    print(f"Surgical Comma Fix - Processing {len(files_with_errors)} files")
    print("=" * 60)

    for i, file_path in enumerate(files_with_errors, 1):
        print(f"[{i}/{len(files_with_errors)}] {file_path.name}...", end=" ")

        if fix_file(file_path):
            print("[OK]")
        else:
            print("[FAIL] - STOPPED")
            return 1

    print("\n" + "=" * 60)
    print("SUCCESS: All files fixed and validated")
    return 0


if __name__ == "__main__":
    sys.exit(main())
