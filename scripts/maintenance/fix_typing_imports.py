#!/usr/bin/env python3
"""
Fix missing typing imports across the codebase.
Adds 'from typing import Optional, List, Dict, Any, Union' to files with NameError.
"""

import re
from pathlib import Path


def has_typing_imports(content: str) -> bool:
    """Check if file already has typing imports."""
    return bool(re.search(r'^from typing import', content, re.MULTILINE))

def needs_typing_fix(content: str) -> set[str]:
    """Detect which typing imports are used but not imported."""
    needed = set()

    # Common typing patterns
    if re.search(r'\bOptional\[', content):
        needed.add('Optional')
    if re.search(r'\bList\[', content):
        needed.add('List')
    if re.search(r'\bDict\[', content):
        needed.add('Dict')
    if re.search(r'\bAny\b', content) and not re.search(r'from typing.*Any', content):
        needed.add('Any')
    if re.search(r'\bUnion\[', content):
        needed.add('Union')
    if re.search(r'\bTuple\[', content):
        needed.add('Tuple')
    if re.search(r'\bCallable\[', content):
        needed.add('Callable')

    return needed

def add_typing_imports(content: str, imports_needed: set[str]) -> str:
    """Add typing imports to file content."""
    if not imports_needed:
        return content

    import_line = f"from typing import {', '.join(sorted(imports_needed))}\n"

    # Find where to insert (after docstring, before first import or code)
    lines = content.split('\n')
    insert_pos = 0
    in_docstring = False
    docstring_char = None

    for i, line in enumerate(lines):
        stripped = line.strip()

        # Handle module docstring
        if i == 0 or (i == 1 and lines[0].startswith('#!')):
            if stripped.startswith('"""') or stripped.startswith("'''"):
                in_docstring = True
                docstring_char = stripped[:3]
                if stripped.count(docstring_char) >= 2:  # Single line docstring
                    in_docstring = False
                    insert_pos = i + 1
                continue

        if in_docstring:
            if docstring_char in line:
                in_docstring = False
                insert_pos = i + 1
            continue

        # Skip shebang and encoding
        if stripped.startswith('#'):
            insert_pos = i + 1
            continue

        # Found first import or code
        if stripped and not stripped.startswith('#'):
            insert_pos = i
            break

    # Insert import
    lines.insert(insert_pos, import_line)
    return '\n'.join(lines)

def fix_file(filepath: Path) -> bool:
    """Fix typing imports in a single file."""
    try:
        content = filepath.read_text(encoding='utf-8')

        # Check if already has typing imports
        if has_typing_imports(content):
            # Still check if additional imports needed
            imports_needed = needs_typing_fix(content)
            if not imports_needed:
                return False

            # Add to existing import
            content = re.sub(
                r'(from typing import [^\n]+)',
                lambda m: f"{m.group(1)}, {', '.join(sorted(imports_needed))}",
                content,
                count=1
            )
        else:
            # No typing imports yet - check if needed
            imports_needed = needs_typing_fix(content)
            if not imports_needed:
                return False

            content = add_typing_imports(content, imports_needed)

        filepath.write_text(content, encoding='utf-8')
        return True

    except Exception as e:
        print(f"Error fixing {filepath}: {e}")
        return False

def main():
    """Fix typing imports across the codebase."""
    # Find all Python files with NameError in test collection
    error_patterns = [
        'tests/rag/*.py',
        'tests/unit/*.py',
        'tests/**/*.py',
        'packages/*/tests/**/*.py',
        'apps/*/tests/**/*.py'
    ]

    fixed_count = 0
    checked_count = 0

    for pattern in error_patterns:
        for filepath in Path('.').glob(pattern):
            if filepath.name.startswith('__'):
                continue

            checked_count += 1
            if fix_file(filepath):
                fixed_count += 1
                print(f"Fixed: {filepath}")

    print(f"\nFixed {fixed_count} files out of {checked_count} checked")

if __name__ == '__main__':
    main()
