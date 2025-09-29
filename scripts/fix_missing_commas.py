#!/usr/bin/env python3
"""
Fix all missing commas in function/class calls and definitions.
This is a common pattern in the Hive codebase causing syntax errors.
"""

import ast
import re
from pathlib import Path


def fix_missing_commas_in_file(file_path: Path) -> bool:
    """Fix missing commas in a single Python file."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Try to parse first to see if there are errors
        try:
            ast.parse(content)
            return True  # No syntax errors
        except SyntaxError as e:
            if "forgot a comma" not in str(e):
                # Different error type
                return False

        lines = content.split("\n")
        fixed_lines = []

        # Track if we're inside a function call, class definition, etc.
        paren_depth = 0
        bracket_depth = 0
        brace_depth = 0

        for i, line in enumerate(lines):
            # Count brackets
            for char in line:
                if char == "(":
                    paren_depth += 1
                elif char == ")":
                    paren_depth -= 1
                elif char == "[":
                    bracket_depth += 1
                elif char == "]":
                    bracket_depth -= 1
                elif char == "{":
                    brace_depth += 1
                elif char == "}":
                    brace_depth -= 1

            # We're inside a multi-line structure
            in_structure = paren_depth > 0 or bracket_depth > 0 or brace_depth > 0

            # Check if line needs a comma
            if in_structure:
                stripped = line.rstrip()
                if stripped and not stripped.endswith((",", ":", "(", "[", "{", ")", "]", "}")):
                    # Check if next line continues the structure
                    if i + 1 < len(lines):
                        next_line = lines[i + 1].strip()
                        # If next line is not empty and not a closing bracket
                        if next_line and next_line[0] not in ")]}" and not next_line.startswith("#"):
                            # Check if this line looks like it should have a comma
                            # Common patterns: key=value, "string", number, identifier
                            if (
                                re.search(r"\w+\s*=\s*.+$", stripped)  # key=value
                                or re.search(r'["\'].+["\']$', stripped)  # string
                                or re.search(r"\d+(\.\d+)?$", stripped)  # number
                                or re.search(r"\w+$", stripped)
                            ):  # identifier
                                line = stripped + ","
                                if len(line) != len(lines[i]):
                                    # Preserve any trailing whitespace/comments
                                    line += lines[i][len(stripped) :]

            fixed_lines.append(line)

        fixed_content = "\n".join(fixed_lines)

        # Verify the fix worked
        try:
            ast.parse(fixed_content)
            # Success! Write it back
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(fixed_content)
            return True
        except SyntaxError:
            # Still broken
            return False

    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return False


def main():
    """Main function to fix all files with missing comma errors."""
    project_root = Path(__file__).parent.parent
    fixed_count = 0
    failed_count = 0

    print("Scanning for files with missing comma errors...")

    for directory in ["packages", "apps"]:
        dir_path = project_root / directory
        if not dir_path.exists():
            continue

        for py_file in dir_path.rglob("*.py"):
            # Skip __pycache__ and backup directories
            if "__pycache__" in str(py_file) or "scripts_backup" in str(py_file):
                continue

            # Check if file has syntax errors
            try:
                with open(py_file, "r", encoding="utf-8") as f:
                    compile(f.read(), str(py_file), "exec")
            except SyntaxError as e:
                if "forgot a comma" in str(e):
                    # Try to fix it
                    if fix_missing_commas_in_file(py_file):
                        print(f"FIXED: {py_file.relative_to(project_root)}")
                        fixed_count += 1
                    else:
                        print(f"FAILED: {py_file.relative_to(project_root)}")
                        failed_count += 1

    print(f"\nFixed {fixed_count} files, Failed {failed_count} files")


if __name__ == "__main__":
    main()
