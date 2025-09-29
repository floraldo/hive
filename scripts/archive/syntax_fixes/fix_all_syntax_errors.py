#!/usr/bin/env python3
"""
Comprehensive syntax error fixing script for the Hive codebase.
Fixes common patterns that cause syntax errors.
"""

import re
from pathlib import Path


class SyntaxErrorFixer:
    """Fix all syntax errors in the codebase."""

    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.fixed_count = 0
        self.failed_count = 0

    def fix_await_outside_async(self, content: str) -> str:
        """Fix 'await' used outside async functions."""
        lines = content.split("\n")
        new_lines = []
        in_function = False
        function_indent = 0
        is_async = False

        for i, line in enumerate(lines):
            # Check if we're entering a function
            if re.match(r"^(\s*)def\s+\w+.*:$", line):
                match = re.match(r"^(\s*)def\s+", line)
                function_indent = len(match.group(1))
                in_function = True
                is_async = False
                new_lines.append(line)
                continue
            elif re.match(r"^(\s*)async\s+def\s+\w+.*:$", line):
                match = re.match(r"^(\s*)async\s+def\s+", line)
                function_indent = len(match.group(1))
                in_function = True
                is_async = True
                new_lines.append(line)
                continue

            # Check if we're still in the function
            if (
                in_function
                and line.strip()
                and not line.startswith(" " * (function_indent + 1))
                and not line.startswith("\t")
            ):
                in_function = False
                is_async = False

            # Fix await in non-async function
            if in_function and not is_async and "await " in line:
                # Check if this function should be async
                if i > 0 and re.match(r"^(\s*)def\s+\w+.*:$", lines[i - 10 : i][-1] if i > 10 else lines[0]):
                    # Look back for the function definition and make it async
                    for j in range(len(new_lines) - 1, -1, -1):
                        if re.match(r"^(\s*)def\s+\w+.*:$", new_lines[j]):
                            new_lines[j] = new_lines[j].replace("def ", "async def ")
                            is_async = True
                            break
                    new_lines.append(line)
                else:
                    # Remove await if we can't make the function async
                    new_lines.append(line.replace("await ", ""))
            else:
                new_lines.append(line)

        return "\n".join(new_lines)

    def fix_missing_commas_in_lists(self, content: str) -> str:
        """Fix missing commas in lists and tuples."""
        # Fix patterns like:
        # (item1, source1)
        # (item2, source2)  <- missing comma
        # (item3, source3)

        lines = content.split("\n")
        new_lines = []

        for i, line in enumerate(lines):
            # Check if line ends with ) and next line starts with whitespace and (
            if line.strip().endswith(")") and not line.strip().endswith(",)"):
                if i + 1 < len(lines):
                    next_line = lines[i + 1]
                    # Check if next line is at same or similar indentation and starts with (
                    if next_line.strip().startswith("("):
                        # Add comma to current line
                        new_lines.append(line.rstrip() + ",")
                        continue
            new_lines.append(line)

        return "\n".join(new_lines)

    def fix_indentation_errors(self, content: str) -> str:
        """Fix common indentation errors."""
        lines = content.split("\n")
        new_lines = []
        expected_indent = 0
        indent_stack = [0]

        for line in lines:
            stripped = line.lstrip()
            if not stripped or stripped.startswith("#"):
                new_lines.append(line)
                continue

            current_indent = len(line) - len(stripped)

            # Handle block starts
            if stripped.endswith(":"):
                new_lines.append(" " * expected_indent + stripped)
                indent_stack.append(expected_indent)
                expected_indent += 4
            # Handle dedents
            elif any(stripped.startswith(kw) for kw in ["else:", "elif ", "except:", "finally:", "except "]):
                if indent_stack:
                    expected_indent = indent_stack[-1]
                new_lines.append(" " * expected_indent + stripped)
                if stripped.endswith(":"):
                    expected_indent += 4
            # Handle returns and breaks
            elif any(stripped.startswith(kw) for kw in ["return", "break", "continue", "pass", "raise"]):
                new_lines.append(" " * expected_indent + stripped)
                if indent_stack and len(indent_stack) > 1:
                    indent_stack.pop()
                    expected_indent = indent_stack[-1] if indent_stack else 0
            # Normal lines
            else:
                # If current indentation is way off, fix it
                if current_indent > expected_indent + 8 or current_indent < expected_indent - 8:
                    new_lines.append(" " * expected_indent + stripped)
                else:
                    new_lines.append(line)

        return "\n".join(new_lines)

    def fix_file(self, file_path: Path) -> bool:
        """Fix a single Python file."""
        try:
            content = file_path.read_text(encoding="utf-8")
            original = content

            # Apply fixes in order
            content = self.fix_missing_commas_in_lists(content)
            content = self.fix_await_outside_async(content)
            content = self.fix_indentation_errors(content)

            # Try to parse to verify it's valid Python
            try:
                compile(content, str(file_path), "exec")
                if content != original:
                    file_path.write_text(content, encoding="utf-8")
                    print(f"FIXED: {file_path.relative_to(self.project_root)}")
                    self.fixed_count += 1
                    return True
            except SyntaxError as e:
                # If still has errors after fixes, report
                print(f"FAILED: {file_path.relative_to(self.project_root)} - {e}")
                self.failed_count += 1
                return False

        except Exception as e:
            print(f"ERROR: {file_path.relative_to(self.project_root)} - {e}")
            self.failed_count += 1
            return False

        return True

    def fix_all(self):
        """Fix all Python files in the project."""
        print("=" * 80)
        print("FIXING ALL SYNTAX ERRORS IN HIVE CODEBASE")
        print("=" * 80)

        for directory in ["packages", "apps"]:
            dir_path = self.project_root / directory
            if dir_path.exists():
                for py_file in dir_path.rglob("*.py"):
                    # Skip __pycache__ and migration files
                    if "__pycache__" in str(py_file) or "migration" in str(py_file):
                        continue

                    # Skip backup directories
                    if "scripts_backup" in str(py_file):
                        continue

                    self.fix_file(py_file)

        print("=" * 80)
        print(f"Fixed: {self.fixed_count} files")
        print(f"Failed: {self.failed_count} files")
        print("=" * 80)


if __name__ == "__main__":
    fixer = SyntaxErrorFixer()
    fixer.fix_all()
