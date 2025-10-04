#!/usr/bin/env python3
# ruff: noqa: S603, S607
# Security: subprocess calls in this script use sys.executable or system tools (git, ruff, etc.) with hardcoded,
# trusted arguments only. No user input is passed to subprocess. This is safe for
# internal maintenance tooling.

"""
Final Comma Fix - Simple and direct

Parse compileall output, fix each file one by one
"""

import subprocess
import sys
from pathlib import Path


def get_files_from_compileall():
    """Get list of files with errors from compileall"""
    result = subprocess.run(
        ["python", "-m", "compileall", "-q", "packages/", "apps/"],
        capture_output=True,
        text=True
    )

    files = set()
    for line in result.stderr.splitlines():
        if line.startswith("*** Error compiling"):
            # Extract path from: *** Error compiling 'path'...
            path = line.split("'")[1]
            # Convert backslashes to forward slashes
            path = path.replace("\\", "/")
            files.add(Path(path))

    return sorted(files)


def fix_file_once(file_path):
    """
    Fix ONE error in a file.

    Returns True if file now compiles, False if more errors remain
    """
    # Compile to get error
    result = subprocess.run(
        ["python", "-m", "py_compile", str(file_path)],
        capture_output=True,
        text=True
    )

    if result.returncode == 0:
        return True  # No errors!

    # Parse error line
    for line in result.stderr.splitlines():
        if "line" in line:
            import re
            match = re.search(r'line (\d+)', line)
            if match:
                error_line = int(match.group(1))
                break
    else:
        print("    Could not parse error line")
        return False

    # Read file
    lines = file_path.read_text(encoding="utf-8").splitlines(keepends=True)

    error_idx = error_line - 1
    error_text = lines[error_idx].strip()

    # Fix based on pattern
    if error_text.startswith('@') and error_text.endswith(','):
        # @staticmethod, -> @staticmethod
        lines[error_idx] = lines[error_idx].rstrip().rstrip(',') + '\n'
    elif '{,' in lines[error_idx]:
        # {, -> {
        lines[error_idx] = lines[error_idx].replace('{,', '{')
    elif '[,' in lines[error_idx]:
        # [, -> [
        lines[error_idx] = lines[error_idx].replace('[,', '[')
    elif '(,' in lines[error_idx]:
        # (, -> (
        lines[error_idx] = lines[error_idx].replace('(,', '(')
    else:
        # Missing comma on previous line
        prev_idx = error_line - 2
        if prev_idx >= 0:
            prev_line = lines[prev_idx]
            if not prev_line.rstrip().endswith(','):
                lines[prev_idx] = prev_line.rstrip() + ',' + '\n'

    # Write
    file_path.write_text(''.join(lines), encoding="utf-8")

    # Check if fixed
    result = subprocess.run(
        ["python", "-m", "py_compile", str(file_path)],
        capture_output=True
    )

    return result.returncode == 0


def main():
    files = get_files_from_compileall()
    print(f"Found {len(files)} files with errors")
    print("=" * 60)

    for i, file_path in enumerate(files, 1):
        print(f"[{i}/{len(files)}] {file_path.name}...")

        # Fix until no more errors (max 20 iterations)
        for iteration in range(20):
            if fix_file_once(file_path):
                print(f"    OK (fixed in {iteration + 1} iterations)")
                break
        else:
            print("    FAILED - max iterations")
            subprocess.run(["git", "restore", str(file_path)])
            return 1

    print("\n" + "=" * 60)
    print("All files fixed!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
