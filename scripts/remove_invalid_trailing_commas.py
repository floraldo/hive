#!/usr/bin/env python3
"""
Remove invalid trailing commas that appeared after the fixer ran.
Specifically: remove commas after opening braces { and after colons :
"""
import re
from pathlib import Path

def fix_invalid_commas(content: str) -> tuple[str, int]:
    """Remove invalid trailing commas"""
    fixes = 0
    original = content

    # Pattern 1: Remove comma after opening brace: {,
    content = re.sub(r'\{\s*,', '{', content)
    if content != original:
        fixes += 1
        original = content

    # Pattern 2: Remove comma after colon: :,
    content = re.sub(r':\s*,\s*\n', ':\n', content)
    if content != original:
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
        new_content, fixes = fix_invalid_commas(content)

        if new_content != content:
            path.write_text(new_content, encoding="utf-8")
            print(f"FIXED: {file_path} ({fixes} invalid commas removed)")
            total_fixes += fixes
        else:
            print(f"OK: {file_path}")

    print(f"\nTotal: {total_fixes} invalid commas removed")
    return 0

if __name__ == "__main__":
    import sys
    sys.exit(main())