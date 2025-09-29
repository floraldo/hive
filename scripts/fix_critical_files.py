#!/usr/bin/env python3
"""
Quick fixer for the 10 most critical files.
Fixes all common comma patterns we've seen.
"""

import re
import sys
from pathlib import Path


def fix_all_comma_patterns(content: str) -> tuple[str, int]:
    """Apply all known comma fix patterns"""
    fixes = 0
    original = content

    # Pattern 1: Function args - arg=value\n spaces arg=value
    for _ in range(100):
        new_content = re.sub(r"(\w+\s*=\s*[^\n,\{\[\(]+)\n(\s+)(\w+\s*=)", r"\1,\n\2\3", content)
        if new_content == content:
            break
        content = new_content
        fixes += 1

    # Pattern 2: Dict entries - "key": value\n spaces "key": value
    for _ in range(100):
        new_content = re.sub(r"(\"[^\"]+\"\s*:\s*[^\n,\{]+)\n(\s+)(\"[^\"]+\"\s*:)", r"\1,\n\2\3", content)
        if new_content == content:
            break
        content = new_content
        fixes += 1

    # Pattern 3: List/tuple items - }\n spaces {
    for _ in range(50):
        new_content = re.sub(r"(\})\n(\s+)(\{)", r"\1,\n\2\3", content)
        if new_content == content:
            break
        content = new_content
        fixes += 1

    # Pattern 4: Path items - Path(...)\n spaces Path(...)
    for _ in range(20):
        new_content = re.sub(r"(Path\([^)]+\))\n(\s+)(Path\([^)]+\))", r"\1,\n\2\3", content)
        if new_content == content:
            break
        content = new_content
        fixes += 1

    # Pattern 5: Remove trailing commas after colons (if statements, etc)
    content = re.sub(r":\s*,\s*\n", ":\n", content)

    return content, fixes


def main():
    critical_files = [
        "apps/ai-planner/src/ai_planner/agent.py",
        "apps/ai-planner/src/ai_planner/async_agent.py",
        "apps/ai-reviewer/src/ai_reviewer/reviewer.py",
        "apps/ai-reviewer/src/ai_reviewer/async_agent.py",
        "apps/ecosystemiser/src/ecosystemiser/main.py",
        "apps/hive-orchestrator/src/hive_orchestrator/async_queen.py",
        "packages/hive-ai/src/hive_ai/agents/agent.py",
        "apps/guardian-agent/src/guardian_agent/cli/main.py",
    ]

    total_fixes = 0

    for file_path in critical_files:
        path = Path(file_path)
        if not path.exists():
            print(f"SKIP: {file_path}")
            continue

        content = path.read_text(encoding="utf-8")
        new_content, fixes = fix_all_comma_patterns(content)

        if new_content != content:
            path.write_text(new_content, encoding="utf-8")
            print(f"FIXED: {file_path} ({fixes} patterns)")
            total_fixes += fixes
        else:
            print(f"OK: {file_path}")

    print(f"\nTotal: {total_fixes} fixes applied")
    return 0


if __name__ == "__main__":
    sys.exit(main())
