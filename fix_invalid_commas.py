#!/usr/bin/env python
"""Fix invalid commas after opening parentheses."""

import re
from pathlib import Path

def fix_invalid_opening_paren_commas(file_path: Path) -> tuple[bool, int]:
    """Remove invalid commas immediately after opening parentheses."""
    content = file_path.read_text(encoding='utf-8')
    original = content
    fixes = 0

    # Pattern: Match "(" followed by "," (with optional whitespace)
    # Examples: "func(," or "Class(,"
    pattern = re.compile(r'\(\s*,')

    def remove_comma(match):
        nonlocal fixes
        fixes += 1
        # Replace "(," with "(" preserving whitespace after
        return '('

    content = pattern.sub(remove_comma, content)

    # Also fix standalone "raise," statements
    raise_pattern = re.compile(r'\braise\s*,\s*$', re.MULTILINE)

    def fix_raise(match):
        nonlocal fixes
        fixes += 1
        return 'raise'

    content = raise_pattern.sub(fix_raise, content)

    if content != original:
        file_path.write_text(content, encoding='utf-8')
        return True, fixes

    return False, 0

def main():
    """Fix all Python files in project."""
    project_root = Path(__file__).parent

    # Find all Python files
    python_files = []
    for pattern in ['apps/**/*.py', 'packages/**/*.py', 'scripts/**/*.py', 'tests/**/*.py']:
        python_files.extend(project_root.glob(pattern))

    total_fixed = 0
    files_modified = 0

    for file_path in python_files:
        if file_path.name == 'fix_invalid_commas.py':
            continue

        modified, fixes = fix_invalid_opening_paren_commas(file_path)
        if modified:
            files_modified += 1
            total_fixed += fixes
            print(f"[OK] {file_path.relative_to(project_root)}: {fixes} fixes")

    print(f"\nProcessed {len(python_files)} files")
    print(f"Modified {files_modified} files")
    print(f"Applied {total_fixed} fixes")

if __name__ == '__main__':
    main()
