#!/usr/bin/env python3
"""
Final Comprehensive Syntax Fixer

Fixes remaining syntax errors using pattern-specific approaches:
1. Argparse add_argument calls
2. Dictionary literals
3. Function signatures
4. Multi-line expressions
"""

import re
from pathlib import Path


class ComprehensiveSyntaxFixer:
    """Fix all common Python syntax error patterns."""

    def __init__(self):
        self.fixed_count = 0
        self.patterns_fixed = {"argparse": 0, "dict_literal": 0, "function_sig": 0, "multiline_expr": 0}

    def fix_file(self, file_path: Path) -> bool:
        """Fix all syntax error patterns in a file."""
        try:
            with open(file_path, encoding="utf-8") as f:
                content = f.read()

            original = content

            # Apply fixes in order
            content = self.fix_argparse_calls(content)
            content = self.fix_dict_literals(content)
            content = self.fix_function_signatures(content)
            content = self.fix_multiline_expressions(content)

            if content != original:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(content)
                print(f"FIXED: {file_path}")
                self.fixed_count += 1
                return True

            return False

        except Exception as e:
            print(f"ERROR: {file_path} - {e}")
            return False

    def fix_argparse_calls(self, content: str) -> str:
        """Fix missing commas in argparse add_argument calls."""
        lines = content.split("\n")
        fixed_lines = []
        in_add_argument = False
        paren_depth = 0

        for i, line in enumerate(lines):
            # Track add_argument context
            if "add_argument(" in line:
                in_add_argument = True
                paren_depth = line.count("(") - line.count(")")

            if in_add_argument:
                paren_depth += line.count("(") - line.count(")")

                # Check if we need to add comma
                stripped = line.rstrip()
                if stripped and not stripped.endswith((",", "(", ")")):
                    # Check next line
                    if i + 1 < len(lines):
                        next_line = lines[i + 1].strip()
                        # Add comma if next line has content and isn't closing paren
                        if next_line and not next_line.startswith(")") and paren_depth > 0:
                            # Check if current line has parameter pattern
                            if (
                                "=" in stripped
                                or stripped.startswith('"')
                                or stripped.startswith("'")
                                or stripped.startswith("--")
                            ):
                                line = stripped + ","
                                self.patterns_fixed["argparse"] += 1

                if paren_depth <= 0:
                    in_add_argument = False

            fixed_lines.append(line)

        return "\n".join(fixed_lines)

    def fix_dict_literals(self, content: str) -> str:
        """Fix missing commas in dictionary literals."""
        lines = content.split("\n")
        fixed_lines = []
        brace_depth = 0

        for i, line in enumerate(lines):
            brace_depth += line.count("{") - line.count("}")

            if brace_depth > 0:
                stripped = line.rstrip()
                # Check for key: value pattern
                if ":" in stripped and not stripped.endswith((",", "{", "}", "[", "]", "(", ")")):
                    # Check next line
                    if i + 1 < len(lines):
                        next_line = lines[i + 1].strip()
                        if next_line and not next_line.startswith("}"):
                            line = stripped + ","
                            self.patterns_fixed["dict_literal"] += 1

            fixed_lines.append(line)

        return "\n".join(fixed_lines)

    def fix_function_signatures(self, content: str) -> str:
        """Fix missing commas in function signatures and calls."""
        lines = content.split("\n")
        fixed_lines = []
        in_signature = False
        paren_depth = 0

        for i, line in enumerate(lines):
            # Detect function definition start
            if re.match(r"^\s*(def|class)\s+\w+\s*\(", line) or re.match(r"^\s*\w+\s*=\s*\w+\(", line):
                in_signature = True
                paren_depth = line.count("(") - line.count(")")

            if in_signature:
                paren_depth += line.count("(") - line.count(")")
                stripped = line.rstrip()

                # Add comma if needed
                if stripped and not stripped.endswith((",", "(", ")", ":", "[", "]", "{", "}")):
                    if i + 1 < len(lines):
                        next_line = lines[i + 1].strip()
                        if next_line and not next_line.startswith(")") and paren_depth > 0:
                            # Check if line has parameter-like content
                            if (
                                ":" in stripped
                                or "=" in stripped
                                or re.search(r"\w+\s*$", stripped)
                                or stripped.startswith('"')
                                or stripped.startswith("'")
                            ):
                                line = stripped + ","
                                self.patterns_fixed["function_sig"] += 1

                if paren_depth <= 0:
                    in_signature = False

            fixed_lines.append(line)

        return "\n".join(fixed_lines)

    def fix_multiline_expressions(self, content: str) -> str:
        """Fix missing commas in general multi-line expressions."""
        lines = content.split("\n")
        fixed_lines = []

        bracket_stack = []  # Track nesting

        for i, line in enumerate(lines):
            # Update bracket tracking
            for char in line:
                if char in "([{":
                    bracket_stack.append(char)
                elif char in ")]}":
                    if bracket_stack:
                        bracket_stack.pop()

            # If we're inside brackets
            if bracket_stack:
                stripped = line.rstrip()

                # Skip if already has comma or closing bracket
                if stripped and not stripped.endswith((",", "(", ")", "[", "]", "{", "}", ":")):
                    # Check next line
                    if i + 1 < len(lines):
                        next_line = lines[i + 1].strip()
                        # Add comma if next line has content and isn't a closing bracket
                        if next_line and not next_line.startswith((")", "]", "}")):
                            # Check if this looks like an expression that needs comma
                            if (
                                re.search(r"\w+\s*$", stripped)  # ends with identifier
                                or re.search(r'["\']$', stripped)  # ends with string
                                or re.search(r"\d+\.?\d*$", stripped)  # ends with number
                                or stripped.endswith((")", "]"))  # ends with closing bracket
                            ):
                                line = stripped + ","
                                self.patterns_fixed["multiline_expr"] += 1

            fixed_lines.append(line)

        return "\n".join(fixed_lines)


def main():
    """Main function."""
    print("=" * 80)
    print("FINAL COMPREHENSIVE SYNTAX FIXER")
    print("=" * 80)

    fixer = ComprehensiveSyntaxFixer()
    project_root = Path(__file__).parent.parent

    # Get list of files with syntax errors from ruff
    import subprocess
    import sys

    try:
        result = subprocess.run(
            [sys.executable, "-m", "ruff", "check", ".", "--output-format=concise"],
            capture_output=True,
            text=True,
            cwd=project_root,
            errors="ignore",
        )

        # Extract files with syntax errors
        error_files = set()
        if result.stdout:
            for line in result.stdout.split("\n"):
                if "invalid-syntax" in line and ":" in line:
                    file_path = line.split(":")[0]
                    error_files.add(file_path)

        print(f"Found {len(error_files)} files with syntax errors")
        print("\nFixing systematically...")

        for file_path_str in sorted(error_files):
            file_path = project_root / file_path_str
            if file_path.exists():
                fixer.fix_file(file_path)

    except Exception as e:
        print(f"Error running ruff: {e}")
        print("Falling back to scan all Python files...")

        # Fallback: scan all Python files
        for py_file in project_root.rglob("*.py"):
            if ".venv" not in str(py_file) and "archive" not in str(py_file):
                fixer.fix_file(py_file)

    print("\n" + "=" * 80)
    print("RESULTS:")
    print(f"Files fixed: {fixer.fixed_count}")
    print("\nPatterns fixed:")
    for pattern, count in fixer.patterns_fixed.items():
        print(f"  {pattern}: {count}")
    print("=" * 80)


if __name__ == "__main__":
    main()
