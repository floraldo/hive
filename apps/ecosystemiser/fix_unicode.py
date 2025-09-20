#!/usr/bin/env python3
"""
Fix Unicode symbols in Python source files to prevent encoding issues.
"""

import os
import sys
from pathlib import Path

def fix_unicode_in_file(filepath):
    """Fix unicode symbols in a single file."""
    replacements = {
        '°C': 'degC',
        '°F': 'degF',
        '°': 'deg',
        '²': '2',
        '³': '3',
        'W/m²': 'W/m2',
        'm³': 'm3',
        'µ': 'u',
        '–': '-',
        '—': '--',
        ''': "'",
        ''': "'",
        '"': '"',
        '"': '"',
        '…': '...',
        '→': '->',
        '←': '<-',
        '↑': '^',
        '↓': 'v',
        '↔': '<->',
        '✓': '[OK]',
        '✗': '[X]',
        '✅': '[PASS]',
        '❌': '[FAIL]',
        '🔧': '[FIX]',
        '📝': '[NOTE]',
        '📦': '[PKG]',
        '🎉': '[SUCCESS]',
        '⚠️': '[WARNING]',
        '⚠': '[WARNING]',
    }
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except UnicodeDecodeError:
        print(f"Skipping {filepath} - encoding issue")
        return False
    
    original_content = content
    for old, new in replacements.items():
        content = content.replace(old, new)
    
    if content != original_content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Fixed: {filepath}")
        return True
    return False

def main():
    """Fix unicode in all Python files."""
    src_dir = Path(__file__).parent / 'src'
    
    if not src_dir.exists():
        print(f"Source directory not found: {src_dir}")
        return 1
    
    fixed_count = 0
    total_count = 0
    
    for py_file in src_dir.rglob('*.py'):
        total_count += 1
        if fix_unicode_in_file(py_file):
            fixed_count += 1
    
    print(f"\nProcessed {total_count} files, fixed {fixed_count} files")
    return 0

if __name__ == '__main__':
    sys.exit(main())