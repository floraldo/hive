#!/usr/bin/env python3
"""
Comprehensive Comma Fixer - Systematic cleanup of missing commas
Handles all patterns identified in the codebase
"""

import re
import sys
from pathlib import Path
from typing import List, Tuple


def fix_function_call_commas(content: str) -> Tuple[str, int]:
    """Fix missing commas in function call arguments"""
    count = 0

    # Pattern: argument ending with ) or ] or " or } or identifier,
    # followed by newline and indentation, then next argument (identifier=)
    pattern = r'(\)|\]|"|\'|\}|\w)\n(\s+)([a-zA-Z_][a-zA-Z0-9_]*=)'

    def replace_func(match):
        nonlocal count
        # Don't add comma if the line before ends with an opening delimiter
        prev_char = match.group(1)
        if prev_char in "([{":
            return match.group(0)
        count += 1
        return f"{match.group(1)},\n{match.group(2)}{match.group(3)}"

    fixed = re.sub(pattern, replace_func, content)
    return fixed, count


def fix_dict_literal_commas(content: str) -> Tuple[str, int]:
    """Fix missing commas in dictionary literals"""
    count = 0

    # Pattern: "key": value followed by newline and next "key":
    pattern = r'(:\s*[^\n,}]+)\n(\s+)("[\w_]+":|\'[\w_]+\':)'

    def replace_func(match):
        nonlocal count
        # Check if value already ends with comma
        value = match.group(1).rstrip()
        if value.endswith(","):
            return match.group(0)
        count += 1
        return f"{value},\n{match.group(2)}{match.group(3)}"

    fixed = re.sub(pattern, replace_func, content)
    return fixed, count


def fix_boolean_condition_commas(content: str) -> Tuple[str, int]:
    """Fix trailing commas in boolean conditions before 'and'/'or'"""
    count = 0

    # Pattern: expression, followed by newline and 'and' or 'or'
    pattern = r"([^,\n]+),\n(\s+)(and|or)\s+"

    def replace_func(match):
        nonlocal count
        expr = match.group(1).strip()
        # Only fix if this looks like a boolean condition
        if any(op in expr for op in ["==", "!=", ">", "<", "in", "is", "("]):
            count += 1
            return f"{expr}\n{match.group(2)}{match.group(3)} "
        return match.group(0)

    fixed = re.sub(pattern, replace_func, content)
    return fixed, count


def fix_list_comprehension_commas(content: str) -> Tuple[str, int]:
    """Fix commas in list comprehensions before 'for'/'if'"""
    count = 0

    # Pattern: expression, followed by newline and 'for' or 'if' (list comp)
    pattern = r"(\[|\{)\n(\s+)([^\n,]+),\n(\s+)(for|if)\s+"

    def replace_func(match):
        nonlocal count
        count += 1
        return f"{match.group(1)}\n{match.group(2)}{match.group(3)}\n{match.group(4)}{match.group(5)} "

    fixed = re.sub(pattern, replace_func, content)
    return fixed, count


def fix_multiline_expression_commas(content: str) -> Tuple[str, int]:
    """Fix missing commas in multiline expressions"""
    count = 0

    # Pattern: closing bracket/paren/brace followed by identifier= on next line
    pattern = r"(\)|\]|\})\n(\s+)([a-zA-Z_][a-zA-Z0-9_]*=)"

    def replace_func(match):
        nonlocal count
        count += 1
        return f"{match.group(1)},\n{match.group(2)}{match.group(3)}"

    fixed = re.sub(pattern, replace_func, content)
    return fixed, count


def fix_positional_arg_commas(content: str) -> Tuple[str, int]:
    """Fix missing commas after positional arguments in function calls"""
    count = 0

    # Pattern: task["id"] or similar followed by newline and keyword arg
    pattern = r'(\w+\["[^"]+"\])\n(\s+)([a-zA-Z_][a-zA-Z0-9_]*=)'

    def replace_func(match):
        nonlocal count
        count += 1
        return f"{match.group(1)},\n{match.group(2)}{match.group(3)}"

    fixed = re.sub(pattern, replace_func, content)
    return fixed, count


def fix_file(file_path: Path) -> Tuple[bool, dict]:
    """Fix a single file and return success status and stats"""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            original = f.read()

        content = original
        stats = {}

        # Apply all fixes in sequence
        content, count = fix_positional_arg_commas(content)
        stats["positional_args"] = count

        content, count = fix_function_call_commas(content)
        stats["function_calls"] = count

        content, count = fix_dict_literal_commas(content)
        stats["dict_literals"] = count

        content, count = fix_boolean_condition_commas(content)
        stats["boolean_conditions"] = count

        content, count = fix_list_comprehension_commas(content)
        stats["list_comprehensions"] = count

        content, count = fix_multiline_expression_commas(content)
        stats["multiline_expressions"] = count

        # Only write if changes were made
        if content != original:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            return True, stats

        return False, {}

    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return False, {}


def get_files_to_fix() -> List[Path]:
    """Get list of Python files that need fixing from files_to_fix.txt"""
    base_path = Path(__file__).parent.parent
    file_list_path = base_path / "scripts" / "files_to_fix.txt"

    files = []
    try:
        with open(file_list_path, "r") as f:
            for line in f:
                file_path = base_path / line.strip()
                if file_path.exists() and file_path.suffix == ".py":
                    files.append(file_path)

        return sorted(files)

    except Exception as e:
        print(f"Error reading file list: {e}")
        return []


def main():
    print("=" * 80)
    print("COMPREHENSIVE COMMA FIXER")
    print("=" * 80)

    # Get files to fix
    files = get_files_to_fix()

    if not files:
        print("No files found with syntax errors")
        return 0

    print(f"Found {len(files)} files with syntax errors")
    print()

    # Fix each file
    total_stats = {
        "positional_args": 0,
        "function_calls": 0,
        "dict_literals": 0,
        "boolean_conditions": 0,
        "list_comprehensions": 0,
        "multiline_expressions": 0,
    }

    files_fixed = 0

    for file_path in files:
        fixed, stats = fix_file(file_path)
        if fixed:
            files_fixed += 1
            total_fixes = sum(stats.values())
            print(f"[OK] {file_path}: {total_fixes} fixes")
            for key, value in stats.items():
                total_stats[key] += value
        else:
            print(f"[--] {file_path}: no changes needed")

    print()
    print("=" * 80)
    print(f"RESULTS: Fixed {files_fixed} files")
    print()
    print("Patterns fixed:")
    for pattern, count in total_stats.items():
        if count > 0:
            print(f"  {pattern}: {count}")
    print("=" * 80)

    return 0 if files_fixed > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
