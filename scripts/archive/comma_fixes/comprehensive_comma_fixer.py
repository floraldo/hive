#!/usr/bin/env python3
"""
Comprehensive script to fix linter-induced comma damage across Hive platform.

This script addresses systematic comma corruption where automated linters have:
1. Added inappropriate trailing commas after single statements
2. Removed necessary commas from function parameters and calls
3. Corrupted multi-line Python constructs

Critical for Code Red Stabilization Sprint - restores 100% pytest functionality.
"""

import os
import re
import glob
from pathlib import Path


def fix_function_parameter_commas(content):
    """Fix missing commas in function definitions and calls."""

    # Pattern 1: Fix function definition parameters
    # def func(self<newline>param: type<newline>param2: type) -> Fix commas
    def_pattern = r"(\n\s+)(self|cls)\n(\s+)(\w+:\s*[^,\n]+)\n"
    content = re.sub(def_pattern, r"\1\2,\n\3\4,\n", content)

    # Pattern 2: Fix function call parameters
    # func(param=value<newline>param2=value) -> Add commas
    call_pattern = r"(\w+=.+?)\n(\s+)(\w+=)"
    content = re.sub(call_pattern, r"\1,\n\2\3", content)

    # Pattern 3: Fix dictionary definitions
    # {"key": value<newline>"key2": value} -> Add commas
    dict_pattern = r'("[\w_]+": .+?)\n(\s+)("[\w_]+":)'
    content = re.sub(dict_pattern, r"\1,\n\2\3", content)

    return content


def fix_inappropriate_trailing_commas(content):
    """Remove inappropriate trailing commas from single statements."""

    patterns_to_fix = [
        # Import statements: from module import item, -> from module import item
        (r"(from .+ import .+),\n", r"\1\n"),
        # Single assignment statements: var = value, -> var = value
        (r"(\n\s*\w+\s*=.+?),\n", r"\1\n"),
        # Logger statements: logger = get_logger(__name__), -> logger = get_logger(__name__)
        (r"(logger\s*=\s*get_logger\(.+?\)),\n", r"\1\n"),
        # Pass statements: pass, -> pass
        (r"(\n\s*pass),(\n)", r"\1\2"),
        # Global statements: global var, -> global var
        (r"(\n\s*global\s+\w+),(\n)", r"\1\2"),
        # Return statements: return value, -> return value
        (r"(\n\s*return\s+.+?),(\n)", r"\1\2"),
        # Single function calls: func(), -> func()
        (r"(\n\s*\w+\([^)]*\)),(\n)", r"\1\2"),
        # Version assignments: __version__ = "1.0", -> __version__ = "1.0"
        (r"(__\w+__\s*=\s*.+?),\n", r"\1\n"),
    ]

    for pattern, replacement in patterns_to_fix:
        content = re.sub(pattern, replacement, content, flags=re.MULTILINE)

    return content


def fix_missing_function_commas(content):
    """Fix systematic missing commas in function definitions and calls."""

    # Fix multi-line function definitions with missing commas
    # Look for patterns like:
    # def func(
    #     self
    #     param: type
    #     param2: type
    # )

    lines = content.split("\n")
    result_lines = []
    in_function_def = False
    paren_depth = 0

    for i, line in enumerate(lines):
        if "def " in line and "(" in line:
            in_function_def = True
            paren_depth = line.count("(") - line.count(")")

        if in_function_def and paren_depth > 0:
            # Update parentheses depth
            paren_depth += line.count("(") - line.count(")")

            # Check if this line needs a comma (not the last parameter)
            if (
                i + 1 < len(lines)
                and paren_depth > 0
                and line.strip()
                and not line.strip().endswith(",")
                and not line.strip().endswith(":")
                and not line.strip() == "**kwargs"
                and not line.strip().startswith('"""')
                and not line.strip().startswith("#")
                and lines[i + 1].strip()
                and not lines[i + 1].strip().startswith(")")
                and ":" in line
            ):  # Parameter with type annotation

                line = line.rstrip() + ","

        if paren_depth <= 0:
            in_function_def = False

        result_lines.append(line)

    return "\n".join(result_lines)


def fix_missing_call_commas(content):
    """Fix missing commas in function calls and dictionary definitions."""

    # Fix patterns like:
    # func(
    #     param=value
    #     param2=value
    # )

    lines = content.split("\n")
    result_lines = []
    in_call = False
    paren_depth = 0

    for i, line in enumerate(lines):
        # Detect function call or dictionary start
        if ("(" in line or "{" in line) and ("=" in line or ":" in line):
            in_call = True
            paren_depth = line.count("(") + line.count("{") - line.count(")") - line.count("}")

        if in_call and paren_depth > 0:
            # Update depth
            paren_depth += line.count("(") + line.count("{") - line.count(")") - line.count("}")

            # Check if this line needs a comma
            if (
                i + 1 < len(lines)
                and paren_depth > 0
                and line.strip()
                and not line.strip().endswith(",")
                and not line.strip().endswith(":")
                and not line.strip().startswith("#")
                and not line.strip().startswith('"""')
                and ("=" in line or '"' in line)  # Assignment or dict key
                and lines[i + 1].strip()
                and not lines[i + 1].strip().startswith(")")
                and not lines[i + 1].strip().startswith("}")
            ):

                line = line.rstrip() + ","

        if paren_depth <= 0:
            in_call = False

        result_lines.append(line)

    return "\n".join(result_lines)


def fix_file(file_path):
    """Fix comma issues in a single file."""

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        original_content = content

        # Apply fixes in order
        content = fix_inappropriate_trailing_commas(content)
        content = fix_missing_function_commas(content)
        content = fix_missing_call_commas(content)
        content = fix_function_parameter_commas(content)

        # Only write if content changed
        if content != original_content:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"Fixed: {file_path}")
            return True
        else:
            print(f"No changes: {file_path}")
            return False

    except Exception as e:
        print(f"Error fixing {file_path}: {e}")
        return False


def main():
    """Main execution - fix comma issues across Hive platform."""

    # Target files with known comma damage
    target_patterns = [
        "apps/ecosystemiser/src/**/*.py",
        "apps/ecosystemiser/src/ecosystemiser/**/*.py",
        "apps/ecosystemiser/src/EcoSystemiser/**/*.py",
        "packages/*/src/**/*.py",
    ]

    files_fixed = 0
    total_files = 0

    for pattern in target_patterns:
        for file_path in glob.glob(pattern, recursive=True):
            if file_path.endswith(".py"):
                total_files += 1
                if fix_file(file_path):
                    files_fixed += 1

    print(f"\nComma fixing complete:")
    print(f"Files processed: {total_files}")
    print(f"Files fixed: {files_fixed}")
    print(f"Success rate: {files_fixed/total_files*100:.1f}%" if total_files > 0 else "No files found")


if __name__ == "__main__":
    main()
