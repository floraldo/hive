"""Fix missing Optional imports in Python files.

Scans all .py files in src/ecosystemiser/ and adds Optional import
when it's used but not imported.
"""

import ast
import re
from pathlib import Path


def has_optional_usage(content: str) -> bool:
    """Check if file uses Optional[...] syntax."""
    return bool(re.search(r"Optional\[", content))


def has_optional_import(content: str) -> bool:
    """Check if file imports Optional from typing."""
    try:
        tree = ast.parse(content)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module == "typing":
                    for alias in node.names:
                        if alias.name == "Optional":
                            return True
    except SyntaxError:
        # File has syntax errors, check with simple string search
        return "from typing import" in content and "Optional" in content.split("from typing import")[1].split("\n")[0]
    return False


def add_optional_to_import(content: str) -> str:
    """Add Optional to existing typing import."""
    lines = content.split("\n")
    modified = False

    for i, line in enumerate(lines):
        # Find typing import line
        if "from typing import" in line and "Optional" not in line:
            # Parse existing imports
            import_part = line.split("from typing import")[1]

            # Handle different import styles
            if "(" in import_part:
                # Multi-line import: from typing import (
                # Find closing paren
                closing_line = i
                for j in range(i, len(lines)):
                    if ")" in lines[j]:
                        closing_line = j
                        break

                # Add Optional before closing paren
                lines[closing_line] = lines[closing_line].replace(")", ", Optional)")
                modified = True
                break
            else:
                # Single line import
                lines[i] = line.rstrip() + ", Optional"
                modified = True
                break

    if not modified:
        # No typing import found, add it after other imports
        import_section_end = 0
        for i, line in enumerate(lines):
            if line.startswith("import ") or line.startswith("from "):
                import_section_end = i + 1
            elif import_section_end > 0 and line.strip() == "":
                break

        if import_section_end > 0:
            lines.insert(import_section_end, "from typing import Optional")
        else:
            # Add at top of file after docstring
            insert_pos = 0
            if lines[0].strip().startswith('"""') or lines[0].strip().startswith("'''"):
                # Find end of docstring
                for i in range(1, len(lines)):
                    if '"""' in lines[i] or "'''" in lines[i]:
                        insert_pos = i + 1
                        break
            lines.insert(insert_pos, "from typing import Optional")

    return "\n".join(lines)


def fix_file(file_path: Path) -> bool:
    """Fix a single file. Returns True if modified."""
    content = file_path.read_text(encoding="utf-8")

    if not has_optional_usage(content):
        return False

    if has_optional_import(content):
        return False

    # Fix the import
    fixed_content = add_optional_to_import(content)

    if fixed_content != content:
        file_path.write_text(fixed_content, encoding="utf-8")
        return True

    return False


def main():
    """Main execution."""
    src_dir = Path(__file__).parent.parent / "src" / "ecosystemiser"

    if not src_dir.exists():
        print(f"ERROR: Source directory not found: {src_dir}")
        return

    print("Scanning for missing Optional imports...")

    fixed_files = []

    for py_file in src_dir.rglob("*.py"):
        try:
            if fix_file(py_file):
                fixed_files.append(py_file.relative_to(src_dir))
                print(f"  FIXED: {py_file.relative_to(src_dir)}")
        except Exception as e:
            print(f"  ERROR processing {py_file.relative_to(src_dir)}: {e}")

    print(f"\nCompleted: {len(fixed_files)} files fixed")

    if fixed_files:
        print("\nFixed files:")
        for f in fixed_files:
            print(f"  - {f}")


if __name__ == "__main__":
    main()
