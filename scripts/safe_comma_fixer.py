#!/usr/bin/env python3
"""
Safe comma fixer - adds missing commas without breaking syntax.

This script uses multiple targeted patterns to fix missing commas in:
- Function call arguments (arg=value\n    arg=value)
- Dictionary literals ("key": value\n    "key": value)
- Dict items in function calls ({key: value\n    key: value})
- Positional arguments followed by keyword arguments

Specifically AVOIDS adding commas after opening braces/parens/brackets.
"""
import re
import sys
from pathlib import Path


def fix_function_arguments(content: str) -> tuple[str, int]:
    """Fix missing commas between function call arguments."""
    fixes = 0

    # Pattern: arg=value\n    arg=value (keyword arguments)
    # Match: word= followed by value, newline, spaces, word=
    # Don't match if line ends with comma or opening brace/paren
    pattern = r'(\w+\s*=\s*[^\n,\{\[\(]+)\n(\s+)(\w+\s*=)'

    for _ in range(50):  # Multiple passes for nested cases
        new_content = re.sub(pattern, r'\1,\n\2\3', content)
        if new_content == content:
            break
        content = new_content
        fixes += 1

    return content, fixes


def fix_dict_literals(content: str) -> tuple[str, int]:
    """Fix missing commas in dictionary literals."""
    fixes = 0

    # Pattern: "key": value\n    "key": value
    # Match: quoted string, colon, value, newline, spaces, quoted string with colon
    pattern = r'(\"[^\"]+\"\s*:\s*[^\n,]+)\n(\s+)(\"[^\"]+\"\s*:)'

    for _ in range(30):
        new_content = re.sub(pattern, r'\1,\n\2\3', content)
        if new_content == content:
            break
        content = new_content
        fixes += 1

    return content, fixes


def fix_task_id_patterns(content: str) -> tuple[str, int]:
    """Fix missing commas after task["id"] patterns."""
    fixes = 0

    # Pattern: task["id"]\n    workflow_id=
    pattern = r'(task\[\"[^\"]+\"\])\n(\s+)(\w+\s*=)'

    for _ in range(20):
        new_content = re.sub(pattern, r'\1,\n\2\3', content)
        if new_content == content:
            break
        content = new_content
        fixes += 1

    return content, fixes


def fix_dict_in_function_calls(content: str) -> tuple[str, int]:
    """Fix missing commas in dict items within function call payloads."""
    fixes = 0

    # Pattern: "key": value\n    "key": value inside function calls
    # More conservative - only if indented significantly (payload dicts)
    pattern = r'(\"[^\"]+\"\s*:\s*[^\n,]+)\n([ ]{16,})(\"[^\"]+\"\s*:)'

    for _ in range(20):
        new_content = re.sub(pattern, r'\1,\n\2\3', content)
        if new_content == content:
            break
        content = new_content
        fixes += 1

    return content, fixes


def fix_enum_values(content: str) -> tuple[str, int]:
    """Fix missing commas in Enum definitions."""
    fixes = 0

    # Pattern: NAME = "value"\n    NAME = "value"
    pattern = r'([A-Z_]+\s*=\s*\"[^\"]+\")\n(\s+)([A-Z_]+\s*=)'

    for _ in range(10):
        new_content = re.sub(pattern, r'\1,\n\2\3', content)
        if new_content == content:
            break
        content = new_content
        fixes += 1

    return content, fixes


def fix_dict_with_list_values(content: str) -> tuple[str, int]:
    """Fix missing commas in dicts with list values."""
    fixes = 0

    # Pattern: "key": [items]\n    "key": [items]
    pattern = r'(\"[^\"]+\"\s*:\s*\[[^\]]+\])\n(\s+)(\"[^\"]+\"\s*:)'

    for _ in range(20):
        new_content = re.sub(pattern, r'\1,\n\2\3', content)
        if new_content == content:
            break
        content = new_content
        fixes += 1

    return content, fixes


def remove_bad_commas(content: str) -> tuple[str, int]:
    """Remove commas that were incorrectly added after opening braces."""
    fixes = 0

    # Pattern: {, or [, or (, at end of line
    patterns = [
        (r'\{,\s*\n', '{\n'),
        (r'\[,\s*\n', '[\n'),
        (r'\(,\s*\n', '(\n'),
    ]

    for pattern, replacement in patterns:
        new_content = re.sub(pattern, replacement, content)
        if new_content != content:
            fixes += 1
            content = new_content

    return content, fixes


def fix_file(filepath: Path) -> tuple[bool, int, str]:
    """
    Fix missing commas in a Python file.

    Returns:
        (success, total_fixes, error_message)
    """
    try:
        content = filepath.read_text(encoding='utf-8')
        original_content = content
        total_fixes = 0

        # Apply all fix patterns
        content, fixes = fix_function_arguments(content)
        total_fixes += fixes

        content, fixes = fix_dict_literals(content)
        total_fixes += fixes

        content, fixes = fix_task_id_patterns(content)
        total_fixes += fixes

        content, fixes = fix_dict_in_function_calls(content)
        total_fixes += fixes

        content, fixes = fix_enum_values(content)
        total_fixes += fixes

        content, fixes = fix_dict_with_list_values(content)
        total_fixes += fixes

        # Remove any bad commas we might have added
        content, fixes = remove_bad_commas(content)
        if fixes > 0:
            total_fixes -= fixes  # Subtract because we're removing bad fixes

        # Only write if we made changes
        if content != original_content:
            filepath.write_text(content, encoding='utf-8')
            return True, total_fixes, ""

        return True, 0, ""

    except Exception as e:
        return False, 0, str(e)


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python safe_comma_fixer.py <file1> [file2] [...]")
        sys.exit(1)

    total_files = 0
    total_fixes = 0
    failed_files = []

    for filepath_str in sys.argv[1:]:
        filepath = Path(filepath_str)

        if not filepath.exists():
            print(f"SKIP: {filepath} (not found)")
            continue

        success, fixes, error = fix_file(filepath)

        if success:
            total_files += 1
            total_fixes += fixes
            if fixes > 0:
                print(f"FIXED: {filepath} ({fixes} patterns)")
            else:
                print(f"OK: {filepath} (no changes needed)")
        else:
            failed_files.append((filepath, error))
            print(f"ERROR: {filepath} - {error}")

    print(f"\nSummary: {total_files} files processed, {total_fixes} total fixes")

    if failed_files:
        print(f"\nFailed files: {len(failed_files)}")
        for filepath, error in failed_files:
            print(f"  {filepath}: {error}")
        sys.exit(1)


if __name__ == '__main__':
    main()