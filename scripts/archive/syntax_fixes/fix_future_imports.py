#!/usr/bin/env python3
"""
Fix misplaced 'from __future__ import' statements in Python files.
"""

from pathlib import Path


def fix_future_imports(file_path: Path) -> bool:
    """Fix misplaced future import statements in a file."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        lines = content.split("\n")
        fixed_lines = []
        future_imports = []
        docstring_end = False
        in_docstring = False
        docstring_quote = None

        # First pass - extract future imports from wrong places
        for i, line in enumerate(lines):
            # Track docstring state
            if not docstring_end:
                if i == 0 and (line.startswith('"""') or line.startswith("'''")):
                    docstring_quote = '"""' if line.startswith('"""') else "'''"
                    if line.count(docstring_quote) == 2:
                        docstring_end = True
                    else:
                        in_docstring = True
                elif in_docstring and docstring_quote in line:
                    docstring_end = True
                    in_docstring = False

            # Check for misplaced future import
            if "from __future__ import" in line and i > 0:
                # This import is misplaced, save it
                future_imports.append(line.strip())
                # Skip this line in the output
                continue

            fixed_lines.append(line)

        # Second pass - insert future imports in the correct place
        if future_imports:
            result_lines = []
            inserted = False

            for i, line in enumerate(fixed_lines):
                # If we have a module docstring, insert after it
                if i == 0 and (line.startswith('"""') or line.startswith("'''")):
                    result_lines.append(line)
                    # Check if docstring ends on same line
                    quote = '"""' if line.startswith('"""') else "'''"
                    if line.count(quote) == 2:
                        # Single-line docstring
                        for imp in future_imports:
                            result_lines.append(imp)
                        result_lines.append("")
                        inserted = True
                    else:
                        # Multi-line docstring, wait for end
                        for j in range(i + 1, len(fixed_lines)):
                            result_lines.append(fixed_lines[j])
                            if quote in fixed_lines[j]:
                                # Found end of docstring
                                for imp in future_imports:
                                    result_lines.append(imp)
                                result_lines.append("")
                                inserted = True
                                # Continue from after the docstring
                                result_lines.extend(fixed_lines[j + 1 :])
                                break
                        break
                elif i == 0:
                    # No docstring, insert at the beginning
                    for imp in future_imports:
                        result_lines.append(imp)
                    result_lines.append("")
                    result_lines.append(line)
                    inserted = True
                else:
                    result_lines.append(line)

            fixed_lines = result_lines

        # Write back
        fixed_content = "\n".join(fixed_lines)

        # Try to compile to verify
        try:
            compile(fixed_content, str(file_path), "exec")
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(fixed_content)
            return True
        except SyntaxError as e:
            print(f"Still has syntax error after fix: {e}")
            return False

    except Exception as e:
        print(f"Error fixing {file_path}: {e}")
        return False


def main():
    """Main function."""
    project_root = Path(__file__).parent.parent
    fixed_count = 0
    failed_count = 0

    for directory in ["packages", "apps"]:
        dir_path = project_root / directory
        if dir_path.exists():
            for py_file in dir_path.rglob("*.py"):
                # Skip __pycache__ and backup directories
                if "__pycache__" in str(py_file) or "scripts_backup" in str(py_file):
                    continue

                # Check if file has misplaced future imports
                try:
                    with open(py_file, "r", encoding="utf-8") as f:
                        content = f.read()

                    # Look for misplaced future imports
                    lines = content.split("\n")
                    has_misplaced = False
                    for i, line in enumerate(lines):
                        if "from __future__ import" in line and i > 3:
                            has_misplaced = True
                            break

                    if has_misplaced:
                        if fix_future_imports(py_file):
                            print(f"FIXED: {py_file.relative_to(project_root)}")
                            fixed_count += 1
                        else:
                            print(f"FAILED: {py_file.relative_to(project_root)}")
                            failed_count += 1

                except Exception:
                    pass

    print(f"\nFixed {fixed_count} files, Failed {failed_count} files")


if __name__ == "__main__":
    main()
