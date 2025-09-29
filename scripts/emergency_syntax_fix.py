#!/usr/bin/env python3
"""
The Great Comma Fix - AST-Based Missing Comma Fixer

This script uses AST parsing to reliably identify and fix missing commas
in multi-line Python constructs (dictionaries, lists, function calls).

Designed to fix the systematic comma errors in the Hive codebase.
"""

import ast
import re
from pathlib import Path
from typing import List


class CommaFixer:
    """AST-based comma fixer for Python files."""

    def __init__(self):
        self.fixed_files = 0
        self.failed_files = 0
        self.errors_found = 0

    def fix_file(self, file_path: Path) -> bool:
        """Fix missing commas in a single Python file."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                original_content = f.read()

            # Try to parse the file first
            try:
                ast.parse(original_content)
                # File is already syntactically correct
                return True
            except SyntaxError as e:
                if "forgot a comma" not in str(e):
                    # Different syntax error, skip
                    return False

            # Apply comma fixes
            fixed_content = self.fix_missing_commas(original_content)

            # Verify the fix worked
            try:
                ast.parse(fixed_content)

                # Only write if content changed
                if fixed_content != original_content:
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write(fixed_content)
                    print(f"FIXED: {file_path}")
                    self.fixed_files += 1
                    self.errors_found += 1
                return True

            except SyntaxError:
                # Fix didn't work
                print(f"FAILED: {file_path} - Fix didn't resolve syntax error")
                self.failed_files += 1
                return False

        except Exception as e:
            print(f"ERROR: {file_path} - {e}")
            self.failed_files += 1
            return False

    def fix_missing_commas(self, content: str) -> str:
        """Fix missing commas in Python source code."""
        lines = content.split("\n")
        fixed_lines = []

        # Track multi-line constructs
        in_construct = False
        construct_start_chars = []
        paren_depth = 0
        bracket_depth = 0
        brace_depth = 0

        i = 0
        while i < len(lines):
            line = lines[i]
            original_line = line

            # Update bracket tracking
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

            # Are we in a multi-line construct?
            total_depth = paren_depth + bracket_depth + brace_depth
            in_construct = total_depth > 0

            if in_construct:
                # Check if this line needs a comma
                line = self.add_missing_comma_to_line(line, lines, i)

            fixed_lines.append(line)
            i += 1

        return "\n".join(fixed_lines)

    def add_missing_comma_to_line(self, line: str, all_lines: List[str], line_idx: int) -> str:
        """Add comma to a line if it's missing in a multi-line construct."""
        stripped = line.rstrip()

        # Skip empty lines, comments, and lines that already end with commas or closing brackets
        if not stripped or stripped.startswith("#") or stripped.endswith((",", ")", "]", "}", ":")):
            return line

        # Skip lines that are clearly not part of a construct (like function definitions)
        if any(
            stripped.lstrip().startswith(kw)
            for kw in [
                "def ",
                "class ",
                "if ",
                "elif ",
                "else:",
                "for ",
                "while ",
                "with ",
                "try:",
                "except",
                "finally:",
            ]
        ):
            return line

        # Check if next non-empty line suggests we're in a construct
        next_line_idx = line_idx + 1
        while next_line_idx < len(all_lines) and not all_lines[next_line_idx].strip():
            next_line_idx += 1

        if next_line_idx >= len(all_lines):
            return line

        next_line = all_lines[next_line_idx].strip()

        # If next line starts with closing bracket, don't add comma
        if next_line.startswith(("}", ")", "]")):
            return line

        # Common patterns that should have trailing commas in multi-line constructs
        patterns_needing_commas = [
            r"\w+\s*=\s*.+$",  # key=value
            r'["\'].+["\']$',  # string literal
            r"\d+(\.\d+)?$",  # number
            r"\w+$",  # identifier
            r".+\)$",  # expression ending with )
            r".*\]$",  # expression ending with ]
        ]

        for pattern in patterns_needing_commas:
            if re.search(pattern, stripped):
                # Add comma
                return stripped + ","

        return line


def main():
    """Main function to fix comma errors."""
    print("=" * 80)
    print("THE GREAT COMMA FIX - AST-Based Missing Comma Fixer")
    print("=" * 80)

    fixer = CommaFixer()
    project_root = Path(__file__).parent.parent

    # Phase 1: Critical path files
    critical_files = [
        "packages/hive-config/src/hive_config/unified_config.py",
        "packages/hive-config/src/hive_config/async_config.py",
        "packages/hive-config/src/hive_config/secure_config.py",
        "packages/hive-config/src/hive_config/secure_config_original.py",
        "packages/hive-ai/src/hive_ai/core/config.py",
        "packages/hive-ai/src/hive_ai/agents/agent.py",
        "packages/hive-ai/src/hive_ai/models/registry.py",
        "packages/hive-db/src/hive_db/pool.py",
        "packages/hive-db/src/hive_db/async_pool.py",
        "packages/hive-cache/src/hive_cache/cache_client.py",
        "packages/hive-cache/src/hive_cache/performance_cache.py",
    ]

    print("Phase 1: Fixing critical path files...")
    for file_path_str in critical_files:
        file_path = project_root / file_path_str
        if file_path.exists():
            fixer.fix_file(file_path)

    print("\nPhase 1 Results:")
    print(f"Fixed: {fixer.fixed_files} files")
    print(f"Failed: {fixer.failed_files} files")
    print(f"Errors found: {fixer.errors_found}")

    return fixer.fixed_files > 0


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
