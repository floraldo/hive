"""Safely add Optional to typing imports where it's used but not imported."""

import ast
import sys
from pathlib import Path


def needs_optional_import(file_path: Path) -> bool:
    """Check if file uses Optional but doesn't import it."""
    try:
        content = file_path.read_text(encoding='utf-8')

        # Quick check: does file use Optional?
        if 'Optional[' not in content:
            return False

        # Parse AST to check imports
        tree = ast.parse(content, filename=str(file_path))

        # Check if Optional is already imported
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == 'typing':
                for alias in node.names:
                    if alias.name == 'Optional':
                        return False  # Already imported

        return True  # Uses Optional but doesn't import it
    except SyntaxError:
        # File has syntax errors, skip it
        return False
    except Exception as e:
        print(f"ERROR analyzing {file_path}: {e}")
        return False


def add_optional_import(file_path: Path) -> bool:
    """Add Optional to existing typing import."""
    try:
        content = file_path.read_text(encoding='utf-8')
        lines = content.split('\n')
        modified = False

        for i, line in enumerate(lines):
            # Find the typing import line
            if 'from typing import' in line and 'Optional' not in line:
                # Simple case: single line import
                # from typing import Any -> from typing import Any, Optional
                lines[i] = line.rstrip() + ', Optional'
                modified = True
                break

        if modified:
            file_path.write_text('\n'.join(lines), encoding='utf-8')
            return True

        return False
    except Exception as e:
        print(f"ERROR fixing {file_path}: {e}")
        return False


def main():
    """Main execution."""
    src_dir = Path(__file__).parent.parent / 'src' / 'ecosystemiser'

    if not src_dir.exists():
        print(f"ERROR: Source directory not found: {src_dir}")
        return 1

    print("Finding files that need Optional import...")

    fixed_count = 0

    for py_file in src_dir.rglob('*.py'):
        if needs_optional_import(py_file):
            if add_optional_import(py_file):
                print(f"  FIXED: {py_file.relative_to(src_dir)}")
                fixed_count += 1

    print(f"\nCompleted: {fixed_count} files fixed")
    return 0


if __name__ == '__main__':
    sys.exit(main())