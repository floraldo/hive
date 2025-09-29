#!/usr/bin/env python3
"""Fix all syntax errors in the ecosystemiser codebase systematically."""

import ast
import re
from pathlib import Path


def find_syntax_errors(file_path: Path) -> list[tuple[int, str]]:
    """Find syntax errors in a Python file."""
    errors = []

    try:
        with open(file_path, encoding="utf-8") as f:
            content = f.read()

        # Try to parse the file
        try:
            ast.parse(content)
        except SyntaxError as e:
            errors.append((e.lineno or 0, str(e.msg)))

            # Common patterns to check
            lines = content.split("\n")

            # Check for missing commas in dictionaries
            for i, line in enumerate(lines, 1):
                # Pattern: "key": value without comma at end (not last item)
                if re.search(r'^\s*"[^"]+"\s*:\s*[^,\s].*[^,}\s]\s*$', line):
                    if i < len(lines) and lines[i].strip() and not lines[i].strip().startswith("}"):
                        if '"' in lines[i] or "'" in lines[i]:
                            errors.append((i, "Missing comma at end of dictionary item"))

                # Pattern: function parameter without comma
                if i > 0 and "def " in lines[i - 1] or (i > 1 and "def " in lines[i - 2]):
                    if re.search(r"^\s+\w+\s*:", line) and "," not in line:
                        if i < len(lines) and re.search(r"^\s+\w+\s*:", lines[i]):
                            errors.append((i, "Missing comma in function parameters"))

                # Pattern: import statement without comma
                if "from " in line and "(" in line:
                    # Multi-line import
                    j = i
                    while j < len(lines) and ")" not in lines[j - 1]:
                        if re.search(r"^\s+\w+\s*$", lines[j - 1]) and j < len(lines):
                            if re.search(r"^\s+\w+", lines[j]):
                                errors.append((j, "Missing comma in import statement"))
                        j += 1

    except Exception as e:
        errors.append((0, f"Error reading file: {e}"))

    return errors


def fix_common_syntax_errors(file_path: Path) -> int:
    """Fix common syntax errors in a file."""
    fixes_made = 0

    try:
        with open(file_path, encoding="utf-8") as f:
            lines = f.readlines()

        original = lines.copy()

        # Fix missing commas in dictionaries
        for i in range(len(lines)):
            line = lines[i]

            # Dictionary items missing commas
            if re.match(r'^\s*"[^"]+"\s*:\s*[^,].*[^,}\s]\s*$', line):
                if i < len(lines) - 1 and lines[i + 1].strip() and not lines[i + 1].strip().startswith("}"):
                    if '"' in lines[i + 1] or "'" in lines[i + 1]:
                        lines[i] = lines[i].rstrip() + ",\n"
                        fixes_made += 1

            # Function parameters missing commas
            if i > 0 and ("def " in lines[i - 1] or (i > 1 and "def " in lines[i - 2])):
                if re.match(r"^\s+\w+\s*:", line) and "," not in line:
                    if i < len(lines) - 1 and re.match(r"^\s+\w+\s*:", lines[i + 1]):
                        lines[i] = lines[i].rstrip() + ",\n"
                        fixes_made += 1

            # Import statements missing commas
            if i > 0 and "from " in lines[i - 1] and "(" in lines[i - 1]:
                if re.match(r"^\s+\w+\s*$", line):
                    if i < len(lines) - 1 and re.match(r"^\s+\w+", lines[i + 1]):
                        lines[i] = lines[i].rstrip() + ",\n"
                        fixes_made += 1

        # Write back if changes were made
        if lines != original:
            with open(file_path, "w", encoding="utf-8") as f:
                f.writelines(lines)

    except Exception as e:
        print(f"Error fixing {file_path}: {e}")

    return fixes_made


def main():
    """Main function to find and fix all syntax errors."""
    src_dir = Path("src/ecosystemiser")
    test_dir = Path("tests")

    all_files = list(src_dir.rglob("*.py")) + list(test_dir.rglob("*.py"))

    print(f"Scanning {len(all_files)} Python files for syntax errors...")

    files_with_errors = []
    total_errors = 0

    # First pass: Find all syntax errors
    for file_path in all_files:
        errors = find_syntax_errors(file_path)
        if errors:
            files_with_errors.append((file_path, errors))
            total_errors += len(errors)
            print(f"\n{file_path}:")
            for line_no, msg in errors[:3]:  # Show first 3 errors
                print(f"  Line {line_no}: {msg}")

    print(f"\n{'-'*60}")
    print(f"Found {total_errors} syntax errors in {len(files_with_errors)} files")

    if files_with_errors:
        print("\nAttempting to fix common syntax errors...")

        total_fixes = 0
        for file_path, _ in files_with_errors:
            fixes = fix_common_syntax_errors(file_path)
            if fixes > 0:
                total_fixes += fixes
                print(f"  Fixed {fixes} issues in {file_path}")

        print(f"\nTotal fixes applied: {total_fixes}")

        # Second pass: Check remaining errors
        print("\nRe-scanning for remaining errors...")
        remaining_errors = 0
        remaining_files = []

        for file_path, _ in files_with_errors:
            errors = find_syntax_errors(file_path)
            if errors:
                remaining_files.append((file_path, errors))
                remaining_errors += len(errors)

        if remaining_errors > 0:
            print(f"\n{remaining_errors} syntax errors remain in {len(remaining_files)} files")
            print("\nFiles still needing manual fixes:")
            for file_path, errors in remaining_files[:10]:
                print(f"  {file_path}: {len(errors)} errors")
        else:
            print("\n✅ All syntax errors fixed!")
    else:
        print("\n✅ No syntax errors found!")

    return len(remaining_files) if files_with_errors else 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
