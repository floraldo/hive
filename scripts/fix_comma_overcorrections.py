#!/usr/bin/env python3
"""Fix over-eager comma additions from the comprehensive fixer"""
import re
from pathlib import Path

def fix_overcorrections(file_path: Path) -> bool:
    """Fix incorrectly added commas"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        original = content

        # Fix: {, → {
        content = re.sub(r'\{,\s*\n', '{\n', content)

        # Fix: [, → [
        content = re.sub(r'\[,\s*\n', '[\n', content)

        # Fix: (, → (
        content = re.sub(r'\(,\s*\n', '(\n', content)

        # Fix: @decorator, → @decorator
        content = re.sub(r'(@[a-zA-Z_][a-zA-Z0-9_]*),\s*\n', r'\1\n', content)

        # Fix: , Tuple → Tuple (bad import fix)
        content = re.sub(r'from typing import [^,]*,\s*ListTuple', 'from typing import List, Tuple', content)

        if content != original:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return True

        return False

    except Exception as e:
        print(f"Error fixing {file_path}: {e}")
        return False

def main():
    base_path = Path(__file__).parent.parent
    file_list_path = base_path / 'scripts' / 'files_to_fix.txt'

    files_fixed = 0
    with open(file_list_path, 'r') as f:
        for line in f:
            file_path = base_path / line.strip()
            if file_path.exists() and file_path.suffix == '.py':
                if fix_overcorrections(file_path):
                    files_fixed += 1
                    print(f"Fixed overcorrections in: {file_path.name}")

    print(f"\nFixed {files_fixed} files")

if __name__ == '__main__':
    main()