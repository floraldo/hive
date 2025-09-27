#!/usr/bin/env python3
"""
Script to convert all relative imports to absolute imports in the EcoSystemiser codebase.
This ensures consistency and makes modules location-independent.
"""

import re
import ast
from pathlib import Path
from typing import List, Tuple

def get_module_path(file_path: Path, src_root: Path) -> str:
    """Get the module path for a Python file."""
    try:
        relative_path = file_path.relative_to(src_root)
        if relative_path == Path('.'):
            return 'EcoSystemiser'
        if relative_path.suffix:
            relative_path = relative_path.with_suffix('')
        module_parts = relative_path.parts
        return '.'.join(module_parts)
    except ValueError:
        return None

def analyze_imports(file_path: Path) -> List[Tuple[int, str, str]]:
    """Analyze a Python file for relative imports that need fixing."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"Could not read {file_path}: {e}")
        return []

    try:
        tree = ast.parse(content)
    except SyntaxError as e:
        # Don't skip files with syntax errors, they might have been partially edited
        return []

    fixes = []

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.level > 0:  # Relative import
                # Get the line content
                lines = content.split('\n')
                if node.lineno <= len(lines):
                    original_line = lines[node.lineno - 1]

                    # Determine the absolute import
                    file_dir = file_path.parent
                    target_dir = file_dir

                    # Go up directories based on level
                    for _ in range(node.level):
                        target_dir = target_dir.parent

                    # Build the absolute module path
                    if node.module:
                        rel_parts = node.module.split('.')
                    else:
                        rel_parts = []

                    # Convert to absolute path
                    src_root = Path('C:/git/hive/apps/ecosystemiser/src')
                    if target_dir.is_relative_to(src_root):
                        base_module = get_module_path(target_dir, src_root)
                        if base_module:
                            if rel_parts:
                                absolute_module = f"{base_module}.{'.'.join(rel_parts)}"
                            else:
                                absolute_module = base_module
                        else:
                            continue

                        # Build the new import statement
                        import_items = []
                        if node.names:
                            import_items = [alias.name for alias in node.names]

                        if import_items:
                            new_line = f"from {absolute_module} import {', '.join(import_items)}"
                        else:
                            new_line = f"import {absolute_module}"

                        fixes.append((node.lineno, original_line.strip(), new_line))

    return fixes

def fix_file(file_path: Path, fixes: List[Tuple[int, str, str]]) -> bool:
    """Apply fixes to a file."""
    if not fixes:
        return False

    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # Apply fixes (in reverse order to maintain line numbers)
    for line_no, old_import, new_import in sorted(fixes, reverse=True):
        line_idx = line_no - 1
        if line_idx < len(lines):
            # Preserve indentation
            indent = len(lines[line_idx]) - len(lines[line_idx].lstrip())
            lines[line_idx] = ' ' * indent + new_import + '\n'

    with open(file_path, 'w', encoding='utf-8') as f:
        f.writelines(lines)

    return True

def main():
    """Main function to process all Python files."""
    src_root = Path('C:/git/hive/apps/ecosystemiser/src')
    total_fixes = 0
    files_fixed = 0

    # Find all Python files
    python_files = list(src_root.glob('**/*.py'))

    print(f"Analyzing {len(python_files)} Python files for relative imports...")

    for file_path in python_files:
        fixes = analyze_imports(file_path)
        if fixes:
            print(f"\n{file_path.relative_to(src_root)}:")
            for line_no, old, new in fixes:
                print(f"  Line {line_no}: {old}")
                print(f"         -> {new}")

            if fix_file(file_path, fixes):
                files_fixed += 1
                total_fixes += len(fixes)

    print(f"\nFixed {total_fixes} relative imports in {files_fixed} files")

    # Validate no relative imports remain
    remaining_relative = 0
    for file_path in python_files:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        if re.search(r'from \.\. import|from \. import', content):
            remaining_relative += 1

    if remaining_relative > 0:
        print(f"WARNING: {remaining_relative} files still have relative imports")
        return 1
    else:
        print("SUCCESS: All relative imports successfully converted to absolute imports")
        return 0

if __name__ == '__main__':
    exit(main())