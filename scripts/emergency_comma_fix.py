#!/usr/bin/env python3
"""
Emergency Comma Fix Script
Systematically adds missing commas to function calls and definitions.
"""

import re
import sys
from pathlib import Path


def fix_missing_commas_in_file(file_path: Path) -> tuple[bool, int]:
    """Fix missing commas in a Python file.

    Returns: (was_modified, fixes_count)
    """
    try:
        content = file_path.read_text(encoding='utf-8')
        original = content
        fixes = 0

        # Pattern 1: Fix function/method parameters missing commas
        # Matches: "    param=value" followed by newline and another param
        # but NOT if it already has a comma or is the last param before )
        pattern1 = re.compile(
            r'^(\s+)([a-z_][a-z0-9_]*\s*=\s*[^,\n]+)(\n\s+[a-z_][a-z0-9_]*\s*=)',
            re.MULTILINE
        )

        def add_comma(match):
            nonlocal fixes
            fixes += 1
            return f"{match.group(1)}{match.group(2)},{match.group(3)}"

        # Apply fix multiple times to handle consecutive lines
        for _ in range(10):  # Max 10 passes
            new_content = pattern1.sub(add_comma, content)
            if new_content == content:
                break
            content = new_content

        # Pattern 2: Fix function definitions - "self" without comma
        pattern2 = re.compile(r'^(\s+def\s+\w+\(\s*self)(\s+\w+:)', re.MULTILINE)
        content = pattern2.sub(r'\1,\2', content)
        if pattern2.search(original):
            fixes += 1

        if content != original:
            file_path.write_text(content, encoding='utf-8')
            return True, fixes

        return False, 0

    except Exception as e:
        print(f"Error processing {file_path}: {e}", file=sys.stderr)
        return False, 0


def main():
    """Fix all Python files in apps/ and packages/"""
    root = Path.cwd()

    total_files = 0
    total_fixes = 0
    modified_files = []

    for pattern in ['apps/**/*.py', 'packages/**/*.py']:
        for file_path in root.glob(pattern):
            if file_path.is_file() and not any(p in file_path.parts for p in ['__pycache__', '.git', 'archive']):
                total_files += 1
                was_modified, fixes = fix_missing_commas_in_file(file_path)
                if was_modified:
                    modified_files.append(file_path)
                    total_fixes += fixes
                    print(f"[OK] {file_path.relative_to(root)}: {fixes} fixes")

    print(f"\n{'='*60}")
    print(f"Processed {total_files} files")
    print(f"Modified {len(modified_files)} files")
    print(f"Applied {total_fixes} fixes")
    print(f"{'='*60}")

    if modified_files:
        print("\nModified files:")
        for f in modified_files[:20]:  # Show first 20
            print(f"  - {f.relative_to(root)}")
        if len(modified_files) > 20:
            print(f"  ... and {len(modified_files) - 20} more")

    return 0 if total_fixes > 0 else 1


if __name__ == '__main__':
    sys.exit(main())
