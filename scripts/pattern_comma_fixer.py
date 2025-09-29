#!/usr/bin/env python3
"""
Pattern Comma Fixer - Apply the exact patterns that worked for database_adapter.py

This fixer applies the patterns learned from successfully fixing database_adapter.py:
1. Dictionary literals: "key": value\n    "next_key": -> "key": value,\n    "next_key":
2. Function argument tuples: arg\n    next_arg -> arg,\n    next_arg
3. SQL column lists: column\n    next_column -> column,\n    next_column
"""

import ast
import re
from pathlib import Path
import shutil

def apply_comma_patterns(content: str) -> str:
    """Apply specific comma patterns."""

    # Pattern 1: Dictionary entries - quoted keys with values
    # "key": value\n    "next_key": -> "key": value,\n    "next_key":
    content = re.sub(
        r'^(\s*"[^"]+"\s*:\s*[^\n,}]+)(\n\s*"[^"]+"\s*:)',
        r'\1,\2',
        content,
        flags=re.MULTILINE
    )

    # Pattern 2: Function argument tuples - bare identifiers in parentheses
    # identifier\n        next_identifier -> identifier,\n        next_identifier
    content = re.sub(
        r'^(\s+[a-zA-Z_][a-zA-Z0-9_]*)\s*(\n\s+[a-zA-Z_][a-zA-Z0-9_]*[\s\n]*[,)])',
        r'\1,\2',
        content,
        flags=re.MULTILINE
    )

    # Pattern 3: Function calls in tuples - function results
    # function(args)\n        next_item -> function(args),\n        next_item
    content = re.sub(
        r'^(\s+[a-zA-Z_][a-zA-Z0-9_]*\([^)]*\))\s*(\n\s+[a-zA-Z_])',
        r'\1,\2',
        content,
        flags=re.MULTILINE
    )

    # Pattern 4: SQL column lists in SELECT statements
    # Process line by line for SQL patterns
    lines = content.split('\n')
    in_select = False
    result_lines = []

    for i, line in enumerate(lines):
        # Detect SELECT statements
        if 'SELECT' in line.upper():
            in_select = True
        elif 'FROM' in line.strip().upper():
            in_select = False

        # Add commas in SELECT column lists
        if (in_select and
            i < len(lines) - 1 and
            line.strip() and
            not line.strip().endswith(',') and
            not line.strip().endswith('(') and
            not 'SELECT' in line.upper() and
            not 'FROM' in lines[i + 1].upper() and
            lines[i + 1].strip() and
            not lines[i + 1].strip().startswith(')')):
            line = line.rstrip() + ','

        result_lines.append(line)

    return '\n'.join(result_lines)

def fix_file_pattern(filepath: Path) -> bool:
    """Fix a file using learned patterns."""
    try:
        # Create backup
        backup_path = filepath.with_suffix(filepath.suffix + '.backup')
        shutil.copy2(filepath, backup_path)

        # Read original
        with open(filepath, 'r', encoding='utf-8') as f:
            original = f.read()

        # Check if already valid
        try:
            ast.parse(original)
            return True  # Already valid
        except SyntaxError as e:
            if 'comma' not in str(e).lower():
                return False  # Not a comma error

        print(f"Fixing {filepath}")

        # Apply patterns
        fixed = apply_comma_patterns(original)

        # Validate fix
        try:
            ast.parse(fixed)

            # Write if changed
            if fixed != original:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(fixed)
                print(f"  SUCCESS: Fixed {filepath}")
                return True
            else:
                print(f"  NO CHANGE: {filepath}")
                return True

        except SyntaxError as e:
            print(f"  FAILED: {filepath} - {e}")
            # Restore original
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(original)
            return False

    except Exception as e:
        print(f"  ERROR: {filepath} - {e}")
        return False

def main():
    """Apply pattern fixes to all syntax error files."""
    print("Pattern Comma Fixer - Applying learned patterns")

    # Get all Python files with syntax errors
    problem_files = []
    patterns = ['apps/**/*.py', 'packages/**/*.py']

    for pattern in patterns:
        files = list(Path('.').glob(pattern))
        for filepath in files:
            if not any(skip in str(filepath) for skip in ['.venv', '__pycache__', '.git']):
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        content = f.read()
                    ast.parse(content)
                except SyntaxError as e:
                    if 'comma' in str(e).lower() or 'perhaps you forgot' in str(e).lower():
                        problem_files.append(filepath)
                except:
                    pass

    print(f"Found {len(problem_files)} files with comma syntax errors")

    fixed = 0
    failed = 0

    for filepath in problem_files:
        if fix_file_pattern(filepath):
            fixed += 1
        else:
            failed += 1

    print(f"\nResults: {fixed} fixed, {failed} failed")
    return 0 if failed == 0 else 1

if __name__ == "__main__":
    import sys
    sys.exit(main())