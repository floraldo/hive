#!/usr/bin/env python3
"""
Surgical fixer for async_agent.py files with cascading comma errors.
Uses tokenizer to handle malformed code.
"""
import re
from pathlib import Path
import tokenize
import io

def fix_function_call_args(content: str) -> tuple[str, int]:
    """Fix missing commas in function call arguments"""
    fixes = 0

    # Pattern: arg=value\n spaces arg=value (inside function calls)
    pattern = r'([a-zA-Z_]\w*\s*=\s*[^\n,\)]+)\n(\s+)([a-zA-Z_]\w*\s*=)'

    for _ in range(100):  # Iterate until no more fixes
        new_content = re.sub(pattern, r'\1,\n\2\3', content)
        if new_content == content:
            break
        content = new_content
        fixes += 1

    return content, fixes

def fix_dict_entries(content: str) -> tuple[str, int]:
    """Fix missing commas in dictionary entries"""
    fixes = 0

    # Pattern: "key": value\n spaces "key": value
    pattern = r'(\"[^\"]+\"\s*:\s*[^\n,\}]+)\n(\s+)(\"[^\"]+\"\s*:)'

    for _ in range(100):
        new_content = re.sub(pattern, r'\1,\n\2\3', content)
        if new_content == content:
            break
        content = new_content
        fixes += 1

    return content, fixes

def fix_closing_parens(content: str) -> tuple[str, int]:
    """Fix missing commas before closing parentheses in multi-line calls"""
    fixes = 0

    # Pattern: value\n spaces ) should be value,\n spaces )
    # But only if the line doesn't already end with comma
    pattern = r'([^\n,\(])\n(\s+)\)'

    for _ in range(50):
        new_content = re.sub(pattern, r'\1,\n\2)', content)
        if new_content == content:
            break
        content = new_content
        fixes += 1

    return content, fixes

def main():
    files = [
        "apps/ai-planner/src/ai_planner/async_agent.py",
        "apps/ai-reviewer/src/ai_reviewer/async_agent.py",
    ]

    total_fixes = 0

    for file_path in files:
        path = Path(file_path)
        if not path.exists():
            print(f"SKIP: {file_path}")
            continue

        content = path.read_text(encoding="utf-8")
        original = content
        file_fixes = 0

        # Apply all fix patterns
        content, f1 = fix_function_call_args(content)
        file_fixes += f1

        content, f2 = fix_dict_entries(content)
        file_fixes += f2

        content, f3 = fix_closing_parens(content)
        file_fixes += f3

        if content != original:
            path.write_text(content, encoding="utf-8")
            print(f"FIXED: {file_path} ({file_fixes} patterns)")
            total_fixes += file_fixes
        else:
            print(f"OK: {file_path}")

    print(f"\nTotal: {total_fixes} fixes applied")
    return 0

if __name__ == "__main__":
    import sys
    sys.exit(main())