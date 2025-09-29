#!/usr/bin/env python3
"""
Fix indentation errors in Python files.
"""

import re
from pathlib import Path


def fix_indentation(file_path: Path) -> bool:
    """Fix indentation errors in a single file."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        fixed_lines = []
        prev_indent = 0
        in_class = False
        in_function = False
        expected_indent = 0

        for i, line in enumerate(lines):
            # Get the current indentation
            stripped = line.lstrip()
            if not stripped or stripped.startswith("#"):
                fixed_lines.append(line)
                continue

            current_indent = len(line) - len(stripped)

            # Check for decorators - they should be at expected indent level
            if stripped.startswith("@"):
                # Decorators should be at the same level as what they decorate
                fixed_lines.append(" " * expected_indent + stripped)
                continue

            # Check for class definitions
            if re.match(r"^class\s+\w+", stripped):
                fixed_lines.append(" " * expected_indent + stripped)
                if stripped.endswith(":"):
                    in_class = True
                    expected_indent += 4
                continue

            # Check for function definitions
            if re.match(r"^(async\s+)?def\s+\w+", stripped):
                fixed_lines.append(" " * expected_indent + stripped)
                if stripped.endswith(":"):
                    in_function = True
                    expected_indent += 4
                continue

            # Check for block keywords
            if any(
                stripped.startswith(kw)
                for kw in ["if ", "elif ", "else:", "for ", "while ", "try:", "except", "finally:", "with "]
            ):
                # These should be at current expected indent
                fixed_lines.append(" " * expected_indent + stripped)
                if stripped.endswith(":"):
                    expected_indent += 4
                continue

            # Check for dedenting keywords
            if any(stripped.startswith(kw) for kw in ["return", "break", "continue", "pass", "raise"]):
                fixed_lines.append(" " * expected_indent + stripped)
                # After these, we might dedent
                if expected_indent >= 4:
                    # Check if we're ending a block
                    next_line_idx = i + 1
                    while next_line_idx < len(lines) and not lines[next_line_idx].strip():
                        next_line_idx += 1

                    if next_line_idx < len(lines):
                        next_stripped = lines[next_line_idx].lstrip()
                        # If next non-empty line is a class/function/decorator, dedent
                        if any(next_stripped.startswith(kw) for kw in ["@", "class ", "def ", "async def"]):
                            expected_indent = max(0, expected_indent - 4)
                continue

            # Handle empty lines between class/function definitions
            if (
                i > 0
                and not lines[i - 1].strip()
                and (
                    stripped.startswith("class ")
                    or stripped.startswith("def ")
                    or stripped.startswith("async def")
                    or stripped.startswith("@")
                )
            ):
                expected_indent = 0
                if stripped.startswith("@"):
                    fixed_lines.append(stripped)
                else:
                    fixed_lines.append(" " * expected_indent + stripped)
                    if stripped.endswith(":"):
                        expected_indent += 4
                continue

            # Default case - maintain or fix indentation
            if current_indent != expected_indent:
                fixed_lines.append(" " * expected_indent + stripped)
            else:
                fixed_lines.append(line)

        # Write back the fixed content
        fixed_content = "".join(fixed_lines)

        # Try to compile to check if it's valid
        try:
            compile(fixed_content, str(file_path), "exec")
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(fixed_content)
            return True
        except SyntaxError:
            return False

    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return False


def main():
    """Main function to fix all files."""
    project_root = Path(__file__).parent.parent
    error_files = []
    fixed_count = 0

    # Find all Python files with indentation errors
    for directory in ["packages", "apps"]:
        dir_path = project_root / directory
        if dir_path.exists():
            for py_file in dir_path.rglob("*.py"):
                # Skip __pycache__ and backup directories
                if "__pycache__" in str(py_file) or "scripts_backup" in str(py_file):
                    continue

                # Try to compile the file to check for errors
                try:
                    with open(py_file, "r", encoding="utf-8") as f:
                        compile(f.read(), str(py_file), "exec")
                except IndentationError:
                    error_files.append(py_file)
                except SyntaxError:
                    pass  # Handle other syntax errors separately

    print(f"Found {len(error_files)} files with indentation errors")

    # Fix each file
    for file_path in error_files:
        if fix_indentation(file_path):
            print(f"FIXED: {file_path.relative_to(project_root)}")
            fixed_count += 1
        else:
            print(f"FAILED: {file_path.relative_to(project_root)}")

    print(f"\nFixed {fixed_count} out of {len(error_files)} files")


if __name__ == "__main__":
    main()
