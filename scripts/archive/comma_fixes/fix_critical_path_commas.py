#!/usr/bin/env python3
"""
Fix missing commas in the critical import path files.
Focus on the specific files blocking test collection.
"""

import ast
import re
from pathlib import Path


def fix_missing_commas_aggressive(file_path: Path) -> bool:
    """Aggressively fix missing commas in Python files."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        lines = content.split("\n")
        fixed_lines = []

        i = 0
        while i < len(lines):
            line = lines[i]

            # Check if we're in a multi-line construct that needs commas
            if (
                ("(" in line and ")" not in line)
                or ("[" in line and "]" not in line)
                or ("{" in line and "}" not in line)
            ):
                # This starts a multi-line construct
                construct_lines = [line]
                j = i + 1
                paren_count = line.count("(") - line.count(")")
                bracket_count = line.count("[") - line.count("]")
                brace_count = line.count("{") - line.count("}")

                # Collect all lines until the construct ends
                while j < len(lines) and (paren_count > 0 or bracket_count > 0 or brace_count > 0):
                    next_line = lines[j]
                    construct_lines.append(next_line)

                    paren_count += next_line.count("(") - next_line.count(")")
                    bracket_count += next_line.count("[") - next_line.count("]")
                    brace_count += next_line.count("{") - next_line.count("}")
                    j += 1

                # Fix commas in this construct
                fixed_construct = fix_construct_commas(construct_lines)
                fixed_lines.extend(fixed_construct)
                i = j
            else:
                fixed_lines.append(line)
                i += 1

        fixed_content = "\n".join(fixed_lines)

        # Test if the fix worked
        try:
            ast.parse(fixed_content)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(fixed_content)
            return True
        except SyntaxError:
            return False

    except Exception as e:
        print(f"Error fixing {file_path}: {e}")
        return False


def fix_construct_commas(lines):
    """Fix commas in a multi-line construct."""
    fixed_lines = []

    for i, line in enumerate(lines):
        stripped = line.rstrip()

        # Skip empty lines and closing brackets
        if not stripped or stripped.endswith(("}", ")", "]")):
            fixed_lines.append(line)
            continue

        # If this line doesn't end with a comma and isn't the last line
        if i < len(lines) - 1 and not stripped.endswith(","):
            next_line = lines[i + 1].strip()

            # Add comma if next line doesn't start with closing bracket or is another parameter
            if next_line and not next_line.startswith(("}", ")", "]")):
                # Common patterns that should have commas
                if (
                    re.search(r"\w+\s*=\s*.+$", stripped)  # key=value
                    or re.search(r'["\'].+["\']$', stripped)  # string
                    or re.search(r"\d+(\.\d+)?$", stripped)  # number
                    or re.search(r"\w+$", stripped)  # identifier
                    or re.search(r"\)$", stripped)
                ):  # closing paren
                    fixed_lines.append(stripped + ",")
                    continue

        fixed_lines.append(line)

    return fixed_lines


def main():
    """Fix the critical path files."""
    project_root = Path(__file__).parent.parent

    # Critical path files that are blocking imports
    critical_files = [
        "packages/hive-config/src/hive_config/secure_config.py",
        "packages/hive-config/src/hive_config/secure_config_original.py",
        "packages/hive-config/src/hive_config/unified_config.py",
        "packages/hive-ai/src/hive_ai/agents/agent.py",
        "packages/hive-ai/src/hive_ai/models/registry.py",
        "packages/hive-cache/src/hive_cache/cache_client.py",
        "packages/hive-cache/src/hive_cache/performance_cache.py",
    ]

    fixed_count = 0
    for file_path_str in critical_files:
        file_path = project_root / file_path_str
        if file_path.exists():
            if fix_missing_commas_aggressive(file_path):
                print(f"FIXED: {file_path_str}")
                fixed_count += 1
            else:
                print(f"FAILED: {file_path_str}")

    print(f"\nFixed {fixed_count} critical files")


if __name__ == "__main__":
    main()
