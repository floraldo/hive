#!/usr/bin/env python3
"""
Final comprehensive comma fixer that handles ALL remaining patterns.
This will fix all syntax errors so ruff format can work.
"""
import re
import sys
from pathlib import Path


def fix_list_items_missing_commas(content: str) -> tuple[str, int]:
    """Fix missing commas between list items like Path(...) Path(...)"""
    fixes = 0
    # Pattern: Path(...)\n spaces Path(...)
    pattern = r"(Path\([^)]+\))\n(\s+)(Path\([^)]+\))"
    for _ in range(50):
        new_content = re.sub(pattern, r"\1,\n\2\3", content)
        if new_content == content:
            break
        content = new_content
        fixes += 1
    return content, fixes


def fix_dict_items_missing_commas(content: str) -> tuple[str, int]:
    """Fix missing commas in dict entries"""
    fixes = 0
    # Pattern: "key": value\n spaces "key": value
    pattern = r"(\"[^\"]+\"\s*:\s*[^\n,\{]+)\n(\s+)(\"[^\"]+\"\s*:)"
    for _ in range(100):
        new_content = re.sub(pattern, r"\1,\n\2\3", content)
        if new_content == content:
            break
        content = new_content
        fixes += 1
    return content, fixes


def fix_function_args_missing_commas(content: str) -> tuple[str, int]:
    """Fix missing commas between function arguments"""
    fixes = 0
    # Pattern: arg=value\n spaces arg=value
    pattern = r"(\w+\s*=\s*[^\n,\{\[\(]+)\n(\s+)(\w+\s*=)"
    for _ in range(100):
        new_content = re.sub(pattern, r"\1,\n\2\3", content)
        if new_content == content:
            break
        content = new_content
        fixes += 1
    return content, fixes


def main():
    """Apply all fixes to files with syntax errors"""

    # Files from ruff format error output
    error_files = [
        "apps/ai-planner/src/ai_planner/async_agent.py",
        "apps/ai-planner/src/ai_planner/claude_bridge.py",
        "apps/ai-reviewer/src/ai_reviewer/async_agent.py",
        "apps/ai-reviewer/src/ai_reviewer/core/errors.py",
        "apps/ai-reviewer/src/ai_reviewer/reviewer.py",
        "apps/ai-reviewer/src/ai_reviewer/robust_claude_bridge.py",
        "apps/ecosystemiser/scripts/demo_advanced_capabilities.py",
    ]

    total_fixes = 0

    for file_path in error_files:
        path = Path(file_path)
        if not path.exists():
            print(f"SKIP: {file_path} (not found)")
            continue

        content = path.read_text(encoding="utf-8")
        original = content
        fixes_this_file = 0

        # Apply all fix patterns
        content, fixes = fix_list_items_missing_commas(content)
        fixes_this_file += fixes

        content, fixes = fix_dict_items_missing_commas(content)
        fixes_this_file += fixes

        content, fixes = fix_function_args_missing_commas(content)
        fixes_this_file += fixes

        if content != original:
            path.write_text(content, encoding="utf-8")
            print(f"FIXED: {file_path} ({fixes_this_file} patterns)")
            total_fixes += fixes_this_file
        else:
            print(f"OK: {file_path} (no changes)")

    print(f"\nTotal fixes applied: {total_fixes}")
    return 0 if total_fixes > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
