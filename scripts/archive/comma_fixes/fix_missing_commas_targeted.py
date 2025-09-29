#!/usr/bin/env python3
"""
Targeted Missing Comma Fixer

Based on the specific patterns observed in the Hive codebase, this script
uses regex-based detection to fix the most common comma errors.
"""

import ast
import re
from pathlib import Path


class TargetedCommaFixer:
    """Targeted comma fixer based on observed patterns."""

    def __init__(self):
        self.fixed_files = 0
        self.failed_files = 0

    def fix_file(self, file_path: Path) -> bool:
        """Fix missing commas in a single Python file."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Check if file has syntax errors
            try:
                ast.parse(content)
                return True  # Already syntactically correct
            except SyntaxError as e:
                if "forgot a comma" not in str(e):
                    return False

            # Apply targeted fixes
            original_content = content
            content = self.fix_function_call_commas(content)
            content = self.fix_dict_list_commas(content)
            content = self.fix_function_def_commas(content)

            # Test if fix worked
            try:
                ast.parse(content)
                if content != original_content:
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write(content)
                    print(f"FIXED: {file_path}")
                    self.fixed_files += 1
                return True
            except SyntaxError:
                print(f"FAILED: {file_path}")
                self.failed_files += 1
                return False

        except Exception as e:
            print(f"ERROR: {file_path} - {e}")
            self.failed_files += 1
            return False

    def fix_function_call_commas(self, content: str) -> str:
        """Fix missing commas in function calls and constructors."""
        lines = content.split("\n")
        fixed_lines = []

        i = 0
        while i < len(lines):
            line = lines[i]

            # Look for function call patterns - line ends with ) but no comma before next line
            if ("(" in line and ")" not in line) or line.strip().endswith("("):
                # This starts a function call, collect until closing paren
                call_lines = [line]
                j = i + 1
                paren_count = line.count("(") - line.count(")")

                while j < len(lines) and paren_count > 0:
                    next_line = lines[j]
                    call_lines.append(next_line)
                    paren_count += next_line.count("(") - next_line.count(")")
                    j += 1

                # Fix commas within this function call
                fixed_call = self.add_commas_to_multiline_construct(call_lines)
                fixed_lines.extend(fixed_call)
                i = j
            else:
                fixed_lines.append(line)
                i += 1

        return "\n".join(fixed_lines)

    def fix_dict_list_commas(self, content: str) -> str:
        """Fix missing commas in dictionaries and lists."""
        lines = content.split("\n")
        fixed_lines = []

        i = 0
        while i < len(lines):
            line = lines[i]

            # Look for dict/list patterns
            if ("{" in line and "}" not in line) or ("[" in line and "]" not in line):
                # This starts a dict/list, collect until closing
                construct_lines = [line]
                j = i + 1
                brace_count = line.count("{") - line.count("}")
                bracket_count = line.count("[") - line.count("]")

                while j < len(lines) and (brace_count > 0 or bracket_count > 0):
                    next_line = lines[j]
                    construct_lines.append(next_line)
                    brace_count += next_line.count("{") - next_line.count("}")
                    bracket_count += next_line.count("[") - next_line.count("]")
                    j += 1

                # Fix commas within this construct
                fixed_construct = self.add_commas_to_multiline_construct(construct_lines)
                fixed_lines.extend(fixed_construct)
                i = j
            else:
                fixed_lines.append(line)
                i += 1

        return "\n".join(fixed_lines)

    def fix_function_def_commas(self, content: str) -> str:
        """Fix missing commas in function definitions."""
        # Pattern: def function(\n    param1: type\n    param2: type\n)
        pattern = r"(def\s+\w+\s*\([^)]*\n(?:\s+[^,\n)]+\n)+\s*\))"

        def fix_def_params(match):
            func_def = match.group(1)
            lines = func_def.split("\n")

            fixed_lines = []
            for i, line in enumerate(lines):
                if i == 0 or i == len(lines) - 1:  # First and last lines
                    fixed_lines.append(line)
                    continue

                stripped = line.strip()
                if stripped and not stripped.endswith(",") and not stripped.endswith(":"):
                    # Add comma to parameter line
                    fixed_lines.append(line.rstrip() + ",")
                else:
                    fixed_lines.append(line)

            return "\n".join(fixed_lines)

        return re.sub(pattern, fix_def_params, content, flags=re.DOTALL)

    def add_commas_to_multiline_construct(self, lines):
        """Add missing commas to a multi-line construct."""
        if len(lines) <= 1:
            return lines

        fixed_lines = []
        for i, line in enumerate(lines):
            # Skip first and last lines of construct
            if i == 0 or i == len(lines) - 1:
                fixed_lines.append(line)
                continue

            stripped = line.strip()

            # Skip empty lines and comments
            if not stripped or stripped.startswith("#"):
                fixed_lines.append(line)
                continue

            # Skip lines that already end with comma or closing bracket
            if stripped.endswith((",", ")", "]", "}", ":")):
                fixed_lines.append(line)
                continue

            # Check if next non-empty line is closing bracket
            next_meaningful_line = None
            for j in range(i + 1, len(lines)):
                next_stripped = lines[j].strip()
                if next_stripped:
                    next_meaningful_line = next_stripped
                    break

            if next_meaningful_line and next_meaningful_line.startswith(("}", ")", "]")):
                # Don't add comma before closing bracket
                fixed_lines.append(line)
                continue

            # Common patterns that should have commas
            needs_comma = (
                re.search(r"\w+\s*=\s*.+$", stripped)  # key=value
                or re.search(r'["\'].+["\']$', stripped)  # string
                or re.search(r"\d+(\.\d+)?$", stripped)  # number
                or re.search(r"\w+$", stripped)  # identifier
                or re.search(r".+\)$", stripped)  # expression with )
            )

            if needs_comma:
                fixed_lines.append(line.rstrip() + ",")
            else:
                fixed_lines.append(line)

        return fixed_lines


def main():
    """Run the targeted comma fixer."""
    print("=" * 80)
    print("TARGETED MISSING COMMA FIXER")
    print("=" * 80)

    fixer = TargetedCommaFixer()
    project_root = Path(__file__).parent.parent

    # Critical path files
    critical_files = [
        "packages/hive-config/src/hive_config/unified_config.py",
        "packages/hive-config/src/hive_config/secure_config.py",
        "packages/hive-config/src/hive_config/secure_config_original.py",
        "packages/hive-ai/src/hive_ai/core/config.py",
        "packages/hive-ai/src/hive_ai/agents/agent.py",
        "packages/hive-cache/src/hive_cache/cache_client.py",
        "packages/hive-cache/src/hive_cache/performance_cache.py",
    ]

    print("Fixing critical path files...")
    for file_path_str in critical_files:
        file_path = project_root / file_path_str
        if file_path.exists():
            fixer.fix_file(file_path)

    print("\nResults:")
    print(f"Fixed: {fixer.fixed_files} files")
    print(f"Failed: {fixer.failed_files} files")

    return fixer.fixed_files > 0


if __name__ == "__main__":
    main()
