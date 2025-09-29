#!/usr/bin/env python3
"""
Targeted Comma Fixer - Focus on the specific patterns causing most syntax errors.

Based on analysis of the 58 failing files, this fixer targets:
1. Dictionary literals with missing commas between key-value pairs
2. SQL query strings with missing commas between columns
3. Function call arguments with missing commas
"""

import ast
import re
from pathlib import Path


def fix_dictionary_patterns(content: str) -> str:
    """Fix missing commas in dictionary literals."""

    # Pattern 1: "key": value\n    "next_key": next_value
    # Look for lines ending with ] or ) or identifier followed by newline and quoted key
    content = re.sub(r'(\s*"[^"]+"\s*:\s*[^\n,}]+)(\n\s*"[^"]+"\s*:)', r"\1,\2", content, flags=re.MULTILINE)

    # Pattern 2: Handle function call results like row[0], row[1], etc.
    content = re.sub(
        r'(\s*"[^"]+"\s*:\s*[a-zA-Z_][a-zA-Z0-9_]*\[[^\]]+\])(\n\s*"[^"]+"\s*:)', r"\1,\2", content, flags=re.MULTILINE
    )

    # Pattern 3: Handle method call results like self._parse_json_field(row[7])
    content = re.sub(
        r'(\s*"[^"]+"\s*:\s*[a-zA-Z_][a-zA-Z0-9_]*\.[a-zA-Z_][a-zA-Z0-9_]*\([^)]+\))(\n\s*"[^"]+"\s*:)',
        r"\1,\2",
        content,
        flags=re.MULTILINE,
    )

    # Pattern 4: Simple identifiers like row[9], row[10]
    content = re.sub(r'(\s*"[^"]+"\s*:\s*row\[\d+\])(\n\s*"[^"]+"\s*:)', r"\1,\2", content, flags=re.MULTILINE)

    return content


def fix_sql_comma_patterns(content: str) -> str:
    """Fix missing commas in SQL SELECT statements."""

    # Pattern: SQL columns without commas
    # id, title, description, created_at, updated_at
    # worker_id, priority  <- Missing comma after updated_at

    # Look for SELECT statements and fix missing commas between columns
    lines = content.split("\n")
    in_select = False
    fixed_lines = []

    for i, line in enumerate(lines):
        # Track if we're in a SELECT statement
        if "SELECT" in line.upper():
            in_select = True
        elif line.strip().startswith("FROM") and in_select:
            in_select = False

        # If in SELECT and line ends with identifier and next line starts with identifier
        if (
            in_select
            and i < len(lines) - 1
            and line.strip()
            and not line.strip().endswith(",")
            and not line.strip().endswith("(")
            and lines[i + 1].strip()
            and not lines[i + 1].strip().startswith("FROM")
        ):
            # Add comma to current line
            line = line.rstrip() + ","

        fixed_lines.append(line)

    return "\n".join(fixed_lines)


def fix_function_arg_patterns(content: str) -> str:
    """Fix missing commas in function arguments."""

    # Pattern: function arguments on separate lines without commas
    content = re.sub(r"(\w+\s*=\s*[^,\n)]+)(\n\s*\w+\s*=)", r"\1,\2", content, flags=re.MULTILINE)

    return content


def fix_file_targeted(filepath: Path) -> bool:
    """Apply targeted fixes to a single file."""
    try:
        # Read original content
        with open(filepath, encoding="utf-8") as f:
            original_content = f.read()

        # Check if file already has syntax errors
        try:
            ast.parse(original_content)
            return True  # Already valid
        except SyntaxError as e:
            if "comma" not in str(e).lower():
                return False  # Not a comma error

        print(f"Fixing {filepath}")

        # Apply all targeted fixes
        fixed_content = original_content
        fixed_content = fix_dictionary_patterns(fixed_content)
        fixed_content = fix_sql_comma_patterns(fixed_content)
        fixed_content = fix_function_arg_patterns(fixed_content)

        # Validate the fix
        try:
            ast.parse(fixed_content)

            # Write only if we made changes
            if fixed_content != original_content:
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(fixed_content)
                print(f"  [OK] Fixed syntax errors in {filepath}")
                return True
            else:
                print(f"  [SKIP] No changes needed for {filepath}")
                return True

        except SyntaxError as e:
            print(f"  [FAIL] Fix didn't resolve syntax error: {e}")
            return False

    except Exception as e:
        print(f"  [ERROR] Failed to process {filepath}: {e}")
        return False


def main():
    """Run targeted comma fixing on known problem files."""
    print("=" * 60)
    print("TARGETED COMMA FIXER")
    print("Fixing the specific patterns causing syntax errors")
    print("=" * 60)

    # List of files that failed in the previous run
    problem_files = [
        "apps/ai-deployer/src/ai_deployer/database_adapter.py",
        "apps/ai-planner/src/ai_planner/claude_bridge.py",
        "apps/ai-reviewer/src/ai_reviewer/robust_claude_bridge.py",
        "apps/ecosystemiser/src/ecosystemiser/cli.py",
        "apps/ecosystemiser/src/ecosystemiser/main.py",
        "apps/ecosystemiser/src/ecosystemiser/worker.py",
    ]

    fixed_count = 0
    failed_count = 0

    for file_path_str in problem_files:
        filepath = Path(file_path_str)
        if filepath.exists():
            if fix_file_targeted(filepath):
                fixed_count += 1
            else:
                failed_count += 1
        else:
            print(f"  [SKIP] File not found: {filepath}")

    print(f"\nResults: {fixed_count} fixed, {failed_count} failed")
    return 0 if failed_count == 0 else 1


if __name__ == "__main__":
    import sys

    sys.exit(main())
