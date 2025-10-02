#!/usr/bin/env python3
"""Fix missing commas after dict unpacking in Python files."""

import sys
import re

def fix_dict_unpacking(content):
    """Fix missing commas after **(metadata or {}) patterns."""
    # Pattern: **(metadata or {}) followed by newline and dict key without comma
    pattern = r'(\*\*\([^)]+\))\s*\n(\s+"[^"]+":)'
    replacement = r'\1,\n\2'
    content = re.sub(pattern, replacement, content)

    return content

if __name__ == "__main__":
    file_path = sys.argv[1]

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    fixed_content = fix_dict_unpacking(content)

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(fixed_content)

    print(f"Fixed {file_path}")
