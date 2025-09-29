#!/usr/bin/env python3
"""
Comprehensive syntax fixer for all common error patterns in the Hive codebase.
"""

import re
from pathlib import Path


class ComprehensiveSyntaxFixer:
    """Fix all common syntax errors in Python files."""

    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.fixed_count = 0
        self.failed_count = 0
        self.error_patterns = []

    def fix_missing_commas_in_lists(self, content: str) -> str:
        """Fix missing commas in lists, tuples, and dictionaries."""
        lines = content.split("\n")
        fixed_lines = []

        in_list = False
        list_indent = 0
        bracket_stack = []

        for i, line in enumerate(lines):
            stripped = line.strip()

            # Track brackets
            for char in line:
                if char in "([{":
                    bracket_stack.append(char)
                elif char in ")]}":
                    if bracket_stack:
                        bracket_stack.pop()

            # Check if we're in a list/tuple/dict
            if bracket_stack:
                in_list = True
            else:
                in_list = False

            # Fix missing comma at end of line
            if in_list and stripped and not stripped.endswith((",", ":", "{", "[", "(", ")", "}", "]")):
                # Check if next line continues the list
                if i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    # If next line is at similar indentation and not a closing bracket
                    if next_line and not next_line.startswith(("]", ")", "}")) and not next_line.startswith("#"):
                        # Add comma
                        fixed_lines.append(line.rstrip() + ",")
                        continue

            fixed_lines.append(line)

        return "\n".join(fixed_lines)

    def fix_missing_commas_in_function_calls(self, content: str) -> str:
        """Fix missing commas in function/class arguments."""
        # Pattern: argument without comma before next argument
        pattern = r'(\w+\s*=\s*["\']?[\w\.]+["\']?)\s+(\w+\s*=)'
        content = re.sub(pattern, r"\1, \2", content)

        # Pattern: ) followed by ( without operator
        pattern = r"\)\s+\("
        lines = content.split("\n")
        fixed_lines = []

        for i, line in enumerate(lines):
            if re.search(r"\)\s+\(", line):
                # Check if it's not a function definition or call
                if not re.search(r"(def|class|if|while|for|with)\s", line):
                    line = re.sub(r"\)(\s+)\(", r"),\1(", line)
            fixed_lines.append(line)

        return "\n".join(fixed_lines)

    def fix_async_await_errors(self, content: str) -> str:
        """Fix await used in non-async functions."""
        lines = content.split("\n")
        fixed_lines = []
        current_function = None
        function_indent = 0
        is_async = False

        for i, line in enumerate(lines):
            # Check for function definitions
            func_match = re.match(r"^(\s*)(async\s+)?def\s+(\w+)", line)
            if func_match:
                function_indent = len(func_match.group(1))
                current_function = func_match.group(3)
                is_async = bool(func_match.group(2))
                fixed_lines.append(line)
                continue

            # Check if we're still in the function
            if current_function:
                if line.strip() and not line[0].isspace():
                    current_function = None
                    is_async = False
                elif line.strip():
                    current_indent = len(line) - len(line.lstrip())
                    if current_indent <= function_indent:
                        current_function = None
                        is_async = False

            # Fix await in non-async function
            if current_function and not is_async and "await " in line:
                # Make the function async
                for j in range(len(fixed_lines) - 1, -1, -1):
                    if f"def {current_function}" in fixed_lines[j]:
                        fixed_lines[j] = fixed_lines[j].replace("def ", "async def ")
                        is_async = True
                        break

            fixed_lines.append(line)

        return "\n".join(fixed_lines)

    def fix_class_and_function_bodies(self, content: str) -> str:
        """Ensure classes and functions have proper bodies."""
        lines = content.split("\n")
        fixed_lines = []

        for i, line in enumerate(lines):
            fixed_lines.append(line)

            # Check if line ends with : (class or function definition)
            if line.strip().endswith(":"):
                # Check if next non-empty line is properly indented
                next_line_idx = i + 1
                while next_line_idx < len(lines):
                    next_line = lines[next_line_idx]
                    if next_line.strip():
                        # Check indentation
                        current_indent = len(line) - len(line.lstrip())
                        next_indent = len(next_line) - len(next_line.lstrip())

                        if next_indent <= current_indent:
                            # Missing body, add pass
                            fixed_lines.append(" " * (current_indent + 4) + "pass")
                        break
                    next_line_idx += 1
                else:
                    # End of file, add pass
                    current_indent = len(line) - len(line.lstrip())
                    fixed_lines.append(" " * (current_indent + 4) + "pass")

        return "\n".join(fixed_lines)

    def fix_indentation(self, content: str) -> str:
        """Fix common indentation errors."""
        lines = content.split("\n")
        fixed_lines = []
        expected_indent = 0

        for i, line in enumerate(lines):
            if not line.strip():
                fixed_lines.append(line)
                continue

            stripped = line.lstrip()
            current_indent = len(line) - len(stripped)

            # Decorators should be at module or class level
            if stripped.startswith("@"):
                # Look ahead to see what it decorates
                next_non_empty = i + 1
                while next_non_empty < len(lines) and not lines[next_non_empty].strip():
                    next_non_empty += 1

                if next_non_empty < len(lines):
                    next_line = lines[next_non_empty].lstrip()
                    if next_line.startswith(("def ", "async def ", "class ")):
                        # Decorator should be at same indent as what it decorates
                        fixed_lines.append(" " * expected_indent + stripped)
                        continue

            # Handle block starts
            if stripped.endswith(":"):
                fixed_lines.append(" " * expected_indent + stripped)
                expected_indent += 4
            # Handle dedents
            elif any(stripped.startswith(kw) for kw in ["else:", "elif ", "except:", "except ", "finally:"]):
                expected_indent = max(0, expected_indent - 4)
                fixed_lines.append(" " * expected_indent + stripped)
                if stripped.endswith(":"):
                    expected_indent += 4
            # Handle returns, etc that end blocks
            elif any(stripped.startswith(kw) for kw in ["return", "break", "continue", "raise", "pass"]):
                fixed_lines.append(" " * expected_indent + stripped)
                # Check if next line dedents
                if i + 1 < len(lines):
                    next_line = lines[i + 1].lstrip()
                    if next_line and not next_line.startswith(" "):
                        expected_indent = 0
            # Handle class and function definitions
            elif stripped.startswith(("class ", "def ", "async def ")):
                expected_indent = 0
                fixed_lines.append(stripped)
                if stripped.endswith(":"):
                    expected_indent = 4
            else:
                fixed_lines.append(" " * expected_indent + stripped)

        return "\n".join(fixed_lines)

    def fix_file(self, file_path: Path) -> bool:
        """Apply all fixes to a single file."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            original = content

            # Apply fixes in order
            content = self.fix_missing_commas_in_lists(content)
            content = self.fix_missing_commas_in_function_calls(content)
            content = self.fix_async_await_errors(content)
            content = self.fix_class_and_function_bodies(content)
            content = self.fix_indentation(content)

            # Try to compile
            try:
                compile(content, str(file_path), "exec")

                if content != original:
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write(content)
                    print(f"FIXED: {file_path.relative_to(self.project_root)}")
                    self.fixed_count += 1
                return True

            except SyntaxError as e:
                # Still has errors
                print(f"FAILED: {file_path.relative_to(self.project_root)} - {e.msg}")
                self.failed_count += 1
                return False

        except Exception as e:
            print(f"ERROR: {file_path.relative_to(self.project_root)} - {e}")
            self.failed_count += 1
            return False

    def run(self):
        """Run the fixer on all Python files."""
        print("=" * 80)
        print("COMPREHENSIVE SYNTAX FIX FOR HIVE CODEBASE")
        print("=" * 80)

        for directory in ["packages", "apps"]:
            dir_path = self.project_root / directory
            if not dir_path.exists():
                continue

            for py_file in dir_path.rglob("*.py"):
                # Skip __pycache__ and backups
                if "__pycache__" in str(py_file) or "scripts_backup" in str(py_file):
                    continue

                # Try to compile to check for errors
                try:
                    with open(py_file, "r", encoding="utf-8") as f:
                        compile(f.read(), str(py_file), "exec")
                except (SyntaxError, IndentationError):
                    # File has errors, try to fix
                    self.fix_file(py_file)

        print("=" * 80)
        print(f"Fixed: {self.fixed_count} files")
        print(f"Failed: {self.failed_count} files")
        print("=" * 80)


if __name__ == "__main__":
    fixer = ComprehensiveSyntaxFixer()
    fixer.run()
